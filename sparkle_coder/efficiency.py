"""Bound request copies while preserving exact, replayable local task history."""
import copy
import json


def preview(text, limit):
    if len(text) <= limit:
        return text
    half = max(100, (limit - 160) // 2)
    return text[:half] + '\n[Result shortened for model context; full output stays in task history. Read a narrower range if needed.]\n' + text[-half:]


def compact_group(group, *, recent=False):
    result = copy.deepcopy(group)
    completed = {m.get('tool_call_id') for m in group if m.get('role') == 'tool'}
    for message in result:
        for call in message.get('tool_calls', []):
            if call.get('id') not in completed:
                continue
            function = call.get('function', {})
            fields = {'write_file': ('content',), 'edit_file': ('old_text', 'new_text')}.get(function.get('name'), ())
            if not fields:
                continue
            try:
                arguments = json.loads(function['arguments'])
            except (ValueError, TypeError):
                continue
            for field in fields:
                value = arguments.get(field)
                if isinstance(value, str) and len(value) > 600:
                    arguments[field] = ('[Historical edit body omitted from this request. The tool result records its outcome. '
                                        f'The original {len(value)} characters remain in saved history; read the current file before editing.]')
            function['arguments'] = json.dumps(arguments, ensure_ascii=False)
        if message.get('role') == 'tool':
            text = message.get('content', '')
            limit = 6000 if recent else 1800
            if not isinstance(text, str) or len(text) <= limit:
                continue
            try:
                data = json.loads(text)
            except (ValueError, TypeError):
                data = None
            if isinstance(data, dict):
                for key in ('content', 'output', 'diff'):
                    if isinstance(data.get(key), str):
                        data[key] = preview(data[key], limit)
                data['context_note'] = 'Large output shortened for model context; full result is saved.'
                text = json.dumps(data, ensure_ascii=False)
            message['content'] = preview(text, limit + 700)
    return result
