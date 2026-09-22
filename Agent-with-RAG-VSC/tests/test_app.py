import importlib


def test_app_imports():
    app_module = importlib.import_module('app')
    assert hasattr(app_module, 'app')
    assert app_module.app is not None


def test_custom_agent_uses_skill_tool_for_weather_query():
    app_module = importlib.import_module('app')
    result = app_module.agent_service.process_message(
        'What is the weather in Paris?',
        'Custom Agent',
        'vector_store',
        'gemma-4-26b-a4b-it',
        3,
        0.7,
        256,
    )
    assert 'Paris' in result['response']
    assert 'I received your message' not in result['response']
    assert any(term in result['response'].lower() for term in ('weather', 'temperature', 'forecast'))
    assert '°C' in result['response'] or 'temperature' in result['response'].lower() or 'forecast' in result['response'].lower()


def test_audit_conversations_have_scoped_event_counts():
    app_module = importlib.import_module('app')
    app_module.agent_service.process_message(
        'What is the weather in Paris?', 'Custom Agent', 'vector_store',
        'gemma-4-26b-a4b-it', 3, 0.7, 128,
    )
    conversation = app_module.agent_service.get_conversations()[-1]
    events = app_module.agent_service.get_events(conversation['conversation_id'])
    assert conversation['event_count'] == len(events)
    assert conversation['event_count'] > 0
    assert conversation['agent_type'] == 'Custom Agent'
    assert conversation['agent_response']


def test_document_ingestion_chunks_and_chat_evidence():
    app_module = importlib.import_module('app')
    source_text = 'marketing strategy ' * 100
    assert len(app_module.vector_service._chunk_text(source_text, chunk_size=120, overlap=20)) > 3
    chat = app_module.app.test_client().post('/api/chat', json={
        'message': 'Find relevant passages about marketing strategy',
        'agent': 'Custom Agent',
        'model': 'gemma-4-26b-a4b-it',
        'doc_threshold': 0.3,
        'rag_chunks': 5,
        'max_turns': 3,
        'temperature': 0.7,
        'max_tokens': 64,
    }).get_json()
    assert any(item.get('source') != 'skills vector store' for item in chat['evidence'])


def test_audit_returns_all_conversations_and_redacts_credentials():
    app_module = importlib.import_module('app')
    service = app_module.agent_service
    service._log('test', 'test', 'credential_test', {'api_key': 'secret', 'max_tokens': 12})
    assert service.logs[-1]['payload']['api_key'] == '****'
    assert service.logs[-1]['payload']['max_tokens'] == 12
    assert len(service.get_conversations()) >= 0


def test_weather_skill_log_contains_similarity_score():
    app_module = importlib.import_module('app')
    service = app_module.agent_service
    service.process_message(
        'How is the weather in Lisbon?', 'Custom Agent', 'vector_store',
        'gemini-2.0-flash', 3, 0.7, 64,
    )
    event = next(log for log in reversed(service.logs) if log.get('event_type') == 'skill_search_result')
    skills = event['payload']['skills']
    assert skills
    assert skills[0]['name'] == 'time-weather-skill'
    assert 0 < skills[0]['score'] <= 1
