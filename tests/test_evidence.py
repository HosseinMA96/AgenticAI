"""Offline tests for which pages count as read (D30)."""

from agent_framework import AgentResponse, Content, Message

from finsight.evidence import retrieved_pages, unread_citations


def _response(*contents) -> AgentResponse:
    return AgentResponse(messages=[Message("tool", list(contents))])


def test_search_results_and_rendered_pages_count_as_read():
    r = AgentResponse(messages=[
        Message("assistant", [Content.from_function_call(call_id="2", name="render_page",
                                                        arguments='{"doc_name": "X", "page": 9}')]),
        Message("tool", [Content.from_function_result(call_id="1", result="[page 76]\na\n\n[page 77]\nb")]),
    ])
    assert retrieved_pages(r) == {9, 76, 77}


def test_citation_never_read_is_flagged():
    r = _response(Content.from_function_result(call_id="1", result="[page 76]\na"))
    assert unread_citations([76, 77], r) == [77]
