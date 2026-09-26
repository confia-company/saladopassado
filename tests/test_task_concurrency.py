import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import app as backend


class TaskConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        for name, value in (
            ('_task_preparation_semaphore', asyncio.Semaphore(5)),
            ('_task_batches', {}),
            ('_task_cache', {}),
        ):
            patcher = patch.object(backend, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.workers = []
        self.user = {
            'username': 'test-user', 'auth_token': 'test-token',
            'apply_times': {}, 'active_answer_ids': {}, 'task_rooms': {},
        }

    async def asyncTearDown(self):
        for worker in self.workers:
            if not worker.done():
                worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)

    def spawn(self, coroutine):
        task = asyncio.create_task(coroutine)
        self.workers.append(task)
        return task

    async def until(self, condition):
        async def poll():
            while not condition():
                await asyncio.sleep(0)
        await asyncio.wait_for(poll(), timeout=3)

    def batch(self, batch_id, ids):
        value = {
            'id': batch_id, 'username': self.user['username'],
            'status': 'running', 'total': len(ids), 'completed_count': 0,
            'tasks': {tid: {'status': 'queued'} for tid in ids},
        }
        backend._task_batches[batch_id] = value
        return value

    async def test_batches_share_five_slots_and_delays_release_them(self):
        started, active, peak = [], 0, 0
        gates = {tid: asyncio.Event() for tid in range(12)}
        batches = []

        async def open_task(tid, **kwargs):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            started.append(tid)
            await asyncio.sleep(0)
            return {'questions': []}

        async def solve(data, tid):
            nonlocal active
            await gates[tid].wait()
            active -= 1
            return {'success': True, 'answers': {'1': {}}}

        with patch.object(backend, '_get_task_detail', side_effect=open_task), \
             patch.object(backend, 'resolve_task_answers', side_effect=solve), \
             patch.object(backend, 'submit_task', new_callable=AsyncMock) as submit:
            for ids in (list(range(6)), list(range(6, 12))):
                existing = asyncio.all_tasks()
                result = await backend.start_tasks_batch_solve(
                    backend.TaskBatchSolveRequest(task_ids=ids, min_time=1, max_time=1), self.user)
                self.workers.extend(asyncio.all_tasks() - existing)
                self.assertEqual(result['total'], 6)
                batches.append(backend._task_batches[result['batch_id']])
            await self.until(lambda: len(started) == 5)
            self.assertEqual(sum(t['status'] == 'queued' for b in batches for t in b['tasks'].values()), 7)
            gates[started[0]].set()
            await self.until(lambda: len(started) == 6)
            self.assertEqual(active, 5)
            for gate in gates.values():
                gate.set()
            await self.until(lambda: all(t['status'] == 'waiting_delay' for b in batches for t in b['tasks'].values()))
            self.assertEqual(peak, 5)
            self.assertEqual(len(started), 12)
            submit.assert_not_awaited()

    async def test_manual_open_and_ai_share_the_limit_without_nested_deadlock(self):
        gate = asyncio.Event()
        started, active, peak = [], 0, 0

        async def work(tid):
            nonlocal active, peak
            started.append(tid)
            active += 1
            peak = max(peak, active)
            try:
                await gate.wait()
                await asyncio.sleep(0)
            finally:
                active -= 1

        async def open_task(tid, **kwargs):
            await work(tid)
            return {'questions': []}

        async def solve(data, tid):
            await work(tid)
            return {'success': True, 'answers': {'1': {}}}

        with patch.object(backend, '_get_task_detail', side_effect=open_task), \
             patch.object(backend, 'resolve_task_answers', side_effect=solve):
            tasks = [self.spawn(backend.ai_fill_task(tid, user=self.user)) for tid in range(6)]
            tasks += [self.spawn(backend.get_task_detail(tid, user=self.user)) for tid in range(6, 9)]
            await self.until(lambda: len(started) == 5)
            gate.set()
            await asyncio.wait_for(asyncio.gather(*tasks), 3)
            self.assertLessEqual(peak, 5)
            self.assertEqual(len(started), 15)  # Six opens + six AI calls + three manual opens.

    async def test_stopped_queued_task_makes_no_external_requests(self):
        batch = self.batch('stopped', [1])
        for _ in range(5):
            await backend._task_preparation_semaphore.acquire()
        with patch.object(backend, '_get_task_detail', new_callable=AsyncMock) as opening, \
             patch.object(backend, 'resolve_task_answers', new_callable=AsyncMock) as solve:
            task = self.spawn(backend._solve_single_task_worker('stopped', 1, self.user, 1, 1))
            await asyncio.sleep(0)
            await backend.stop_tasks_batch('stopped', user=self.user)
            for _ in range(5):
                backend._task_preparation_semaphore.release()
            await asyncio.wait_for(task, 3)
            opening.assert_not_awaited()
            solve.assert_not_awaited()
            self.assertEqual(batch['tasks'][1]['status'], 'stopped')
            self.assertEqual(batch['completed_count'], 1)

    async def test_stop_during_opening_skips_ai(self):
        batch = self.batch('stopped', [1])
        gate, entered = asyncio.Event(), asyncio.Event()

        async def open_task(*args, **kwargs):
            entered.set()
            await gate.wait()
            return {'questions': []}

        with patch.object(backend, '_get_task_detail', side_effect=open_task), \
             patch.object(backend, 'resolve_task_answers', new_callable=AsyncMock) as solve:
            task = self.spawn(backend._solve_single_task_worker('stopped', 1, self.user, 1, 1))
            await asyncio.wait_for(entered.wait(), 3)
            await backend.stop_tasks_batch('stopped', user=self.user)
            gate.set()
            await asyncio.wait_for(task, 3)
            solve.assert_not_awaited()
            self.assertEqual(batch['tasks'][1]['status'], 'stopped')

    async def test_errors_and_cancellation_release_slots(self):
        entered = []
        gates = [asyncio.Event() for _ in range(7)]

        async def open_task(tid, **kwargs):
            entered.append(tid)
            await gates[tid].wait()
            if tid == 0:
                raise RuntimeError('CAPTCHA timeout')
            return {'questions': []}

        with patch.object(backend, '_get_task_detail', side_effect=open_task):
            tasks = [self.spawn(backend.get_task_detail(tid, user=self.user)) for tid in range(7)]
            await self.until(lambda: len(entered) == 5)
            gates[0].set()
            await self.until(lambda: len(entered) == 6)
            tasks[1].cancel()
            await self.until(lambda: len(entered) == 7)
            for gate in gates:
                gate.set()
            results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 3)
            self.assertIsInstance(results[0], RuntimeError)
            self.assertIsInstance(results[1], asyncio.CancelledError)
            self.assertTrue(all(isinstance(result, dict) for result in results[2:]))

    async def test_submissions_are_unlimited_but_reopening_is_limited(self):
        opening_gate, sending_gate = asyncio.Event(), asyncio.Event()
        opened, opening, peak_opening, sending = 0, 0, 0, 0
        for tid in range(12):
            backend._task_cache[(self.user['username'], tid)] = {'questions': []}

        class Response:
            status_code = 200
            text = 'response'

            def json(self):
                return {'answer': {'id': 42}, 'id': 42}

        class Client:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def put(self, *args, **kwargs):
                nonlocal sending
                sending += 1
                await sending_gate.wait()
                return Response()

        async def apply(*args, **kwargs):
            nonlocal opened, opening, peak_opening
            opened += 1
            opening += 1
            peak_opening = max(peak_opening, opening)
            await opening_gate.wait()
            await asyncio.sleep(0)
            opening -= 1
            return Response()

        with patch.object(backend, 'HttpCloakClient', Client), \
             patch.object(backend, 'tms_apply_with_captcha', side_effect=apply):
            tasks = [self.spawn(backend.submit_task(tid, backend.SubmitRequest(answers={}), self.user)) for tid in range(12)]
            await self.until(lambda: opened == 5)
            self.assertEqual(sending, 0)
            opening_gate.set()
            await self.until(lambda: sending == 12)
            self.assertEqual(peak_opening, 5)
            sending_gate.set()
            results = await asyncio.wait_for(asyncio.gather(*tasks), 3)
            self.assertTrue(all(result['success'] for result in results))


if __name__ == '__main__':
    unittest.main()
