import json
import unittest
from unittest import mock

import agent


def call(name, args, ident='call-1'):
    return {'id': ident, 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}


class AgentTests(unittest.TestCase):
    def test_model_selects_tools_and_receives_real_result(self):
        seen, events = [], []
        def model(key, name, messages, tools):
            seen.append((key, name, list(messages), tools))
            if len(seen) == 1:
                return {'role': 'assistant', 'content': None, 'tool_calls': [call('run_python', {'code': 'print(42)'})]}
            return {'role': 'assistant', 'content': '结果是 42。'}
        agent.run_agent('计算 42', 'test-key', 'deepseek-chat', ['run_python'], events.append,
                        model_call=model, execute=lambda code: {'status': 'ok', 'stdout': '42\n'})
        self.assertEqual(seen[0][0], 'test-key')
        self.assertEqual(seen[0][3][0]['function']['name'], 'run_python')
        self.assertEqual(json.loads(seen[1][2][-1]['content'])['stdout'], '42\n')
        self.assertEqual(events[-2]['content'], '结果是 42。')
        self.assertEqual(events[-1]['type'], 'done')
        self.assertNotIn('test-key', json.dumps(events))

    def test_disabled_tool_is_not_executed(self):
        events, count = [], 0
        def model(key, name, messages, tools):
            nonlocal count
            count += 1
            return {'role': 'assistant', 'content': None, 'tool_calls': [call('run_python', {'code': 'print(1)'})]} if count == 1 else {'role': 'assistant', 'content': '无法运行代码。'}
        execute = mock.Mock()
        agent.run_agent('计算', 'key', 'deepseek-chat', [], events.append, model_call=model, execute=execute)
        execute.assert_not_called()
        self.assertEqual(next(x for x in events if x['type']=='tool_result')['result']['status'], 'error')

    def test_tool_call_limit(self):
        count = 0
        def model(key, name, messages, tools):
            nonlocal count
            count += 1
            return {'role':'assistant','content':None,'tool_calls':[call('search_papers', {'query':'test'}, str(count))]} if tools else {'role':'assistant','content':'完成'}
        search=mock.Mock(return_value={'items':[]})
        agent.run_agent('查文献','key','deepseek-chat',['search_papers'],lambda e:None,model_call=model,search=search)
        self.assertEqual(search.call_count,agent.MAX_TOOL_CALLS)


class SandboxTests(unittest.TestCase):
    def test_real_container_is_isolated_and_computes(self):
        result=agent.run_python('import socket\nprint(sum(i*i for i in range(1,101)))\ntry:\n socket.create_connection(("1.1.1.1",53),timeout=2)\n print("NETWORK_AVAILABLE")\nexcept OSError:\n print("NETWORK_BLOCKED")')
        self.assertEqual(result['status'], 'ok', result)
        self.assertIn('338350', result['stdout'])
        self.assertIn('NETWORK_BLOCKED', result['stdout'])
        self.assertNotIn('NETWORK_AVAILABLE', result['stdout'])

    def test_timeout_stops_container(self):
        with mock.patch.object(agent, 'RUN_TIMEOUT', 3):
            result=agent.run_python('while True: pass')
        self.assertEqual(result['status'], 'timeout', result)


if __name__=='__main__': unittest.main()
