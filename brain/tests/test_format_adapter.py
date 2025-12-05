
import json
import pytest
from src.adapter.format_adapter import SmartFormatAdapter, normalize_plan

class TestSmartFormatAdapter:
    def test_normalize_minimal_plan(self):
        minimal = {
            'base_url': 'http://api.test.com',
            'tests': [{'http': {'method': 'GET', 'path': '/health'}, 'assertions': [{'type': 'status', 'expected': 200}]}]
        }
        adapter = SmartFormatAdapter()
        result = adapter.normalize(minimal)
        assert result['spec_version'] == '0.1'
        assert 'steps' in result
        assert result['config']['base_url'] == 'http://api.test.com'

    def test_normalize_assertion_type_aliases(self):
        plan = {
            'base_url': 'http://api.test.com',
            'tests': [{'http': {'method': 'GET', 'path': '/h'}, 'assertions': [{'type': 'status', 'expected': 200}]}]
        }
        adapter = SmartFormatAdapter()
        result = adapter.normalize(plan)
        assert result['steps'][0]['assertions'][0]['type'] == 'status_code'

    def test_normalize_extraction_aliases(self):
        plan = {
            'base_url': 'http://api.test.com',
            'tests': [{'http': {'method': 'POST', 'path': '/login'}, 'exports': [{'from': 'body', 'path': 'token', 'name': 'auth_token'}]}]
        }
        adapter = SmartFormatAdapter()
        result = adapter.normalize(plan)
        assert result['steps'][0]['extract'][0]['target'] == 'auth_token'

class TestNormalizePlanFunction:
    def test_normalize_dict(self):
        plan_dict = {'base_url': 'http://api.test.com', 'tests': [{'http': {'method': 'GET', 'path': '/health'}}]}
        result = normalize_plan(plan_dict)
        assert result['spec_version'] == '0.1'

    def test_normalize_json_file(self, tmp_path):
        plan_file = tmp_path / 'plan.json'
        plan_file.write_text(json.dumps({'base_url': 'http://api.test.com', 'tests': [{'http': {'method': 'GET', 'path': '/h'}}]}))
        result = normalize_plan(str(plan_file))
        assert 'steps' in result

class TestEdgeCases:
    def test_no_steps_raises_error(self):
        with pytest.raises(ValueError):
            normalize_plan({'base_url': 'http://api.test.com'})
