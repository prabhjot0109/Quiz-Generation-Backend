from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import wait_for_source_ready


async def _create_ready_source(client: AsyncClient) -> str:
    response = await client.post(
        "/v1/sources",
        json={
            "title": "Learning Science",
            "text": (
                "Formative assessment uses regular feedback to guide learning. "
                "Adaptive quizzes raise difficulty after repeated success and lower it "
                "after repeated mistakes. "
                "Clear rubrics help evaluate short answers consistently."
            ),
        },
    )
    source_id = response.json()["id"]
    detail = await wait_for_source_ready(client, source_id)
    assert detail["status"] == "ready"
    return source_id


async def test_quiz_flow_and_adaptivity(client: AsyncClient) -> None:
    source_id = await _create_ready_source(client)
    create_response = await client.post(
        "/v1/quiz-sessions",
        json={
            "source_id": source_id,
            "question_count": 4,
            "question_types": ["mcq", "true_false", "fill_blank", "short_answer"],
        },
    )
    assert create_response.status_code == 201
    session = create_response.json()
    session_id = session["id"]

    q1 = (await client.get(f"/v1/quiz-sessions/{session_id}/next-question")).json()["question"]
    correct_choice_id = next(
        option["id"] for option in q1["options"] if option["text"] == q1["explanation"]
    )
    answer1 = await client.post(
        f"/v1/quiz-sessions/{session_id}/answers/{q1['id']}",
        json={"answer": {"choice_id": correct_choice_id}},
    )
    assert answer1.status_code == 201
    assert answer1.json()["is_correct"] is True

    q2 = (await client.get(f"/v1/quiz-sessions/{session_id}/next-question")).json()["question"]
    answer2 = await client.post(
        f"/v1/quiz-sessions/{session_id}/answers/{q2['id']}",
        json={"answer": {"value": "true"}},
    )
    assert answer2.status_code == 201
    assert answer2.json()["next_difficulty"] == "hard"

    q3 = (await client.get(f"/v1/quiz-sessions/{session_id}/next-question")).json()["question"]
    answer3 = await client.post(
        f"/v1/quiz-sessions/{session_id}/answers/{q3['id']}",
        json={"answer": {"value": q3["explanation"].split()[-1].strip(".")}},
    )
    assert answer3.status_code == 201

    q4 = (await client.get(f"/v1/quiz-sessions/{session_id}/next-question")).json()["question"]
    answer4 = await client.post(
        f"/v1/quiz-sessions/{session_id}/answers/{q4['id']}",
        json={"answer": {"value": "This answer mentions feedback and adaptive quizzes."}},
    )
    assert answer4.status_code == 201
    assert answer4.json()["session_completed"] is True

    session_detail = await client.get(f"/v1/quiz-sessions/{session_id}")
    assert session_detail.status_code == 200
    assert session_detail.json()["status"] == "completed"


async def test_two_incorrect_answers_reduce_difficulty(client: AsyncClient) -> None:
    source_id = await _create_ready_source(client)
    create_response = await client.post(
        "/v1/quiz-sessions",
        json={
            "source_id": source_id,
            "question_count": 2,
            "question_types": ["true_false", "true_false"],
        },
    )
    session_id = create_response.json()["id"]

    q1 = (await client.get(f"/v1/quiz-sessions/{session_id}/next-question")).json()["question"]
    await client.post(
        f"/v1/quiz-sessions/{session_id}/answers/{q1['id']}",
        json={"answer": {"value": "false"}},
    )

    q2 = (await client.get(f"/v1/quiz-sessions/{session_id}/next-question")).json()["question"]
    assert q2["prompt"] != q1["prompt"]

    answer2 = await client.post(
        f"/v1/quiz-sessions/{session_id}/answers/{q2['id']}",
        json={"answer": {"value": "false"}},
    )
    assert answer2.status_code == 201
    assert answer2.json()["next_difficulty"] == "easy"
