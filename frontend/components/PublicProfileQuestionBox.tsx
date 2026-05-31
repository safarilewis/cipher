"use client";

import { useState, useTransition } from "react";
import { Send, Sparkles } from "lucide-react";
import type { PublicProfileQuestionAnswer } from "@/lib/types";

function titleCase(value: string) {
  return value
    .replace(/[_-]/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function PublicProfileQuestionBox({ slug }: { slug: string }) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<PublicProfileQuestionAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function askQuestion() {
    const trimmed = question.trim();
    if (!trimmed || pending) return;
    setError(null);
    startTransition(async () => {
      try {
        const response = await fetch(`/api/public/profiles/${slug}/ask`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ question: trimmed })
        });
        if (!response.ok) {
          throw new Error("Unable to answer this question right now.");
        }
        setAnswer((await response.json()) as PublicProfileQuestionAnswer);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to answer this question right now.");
      }
    });
  }

  return (
    <section className="panel stack recruiter-question-panel">
      <div className="recruiter-question-head">
        <span className="status"><Sparkles size={14} /> Recruiter check</span>
        <h2>Ask the profile</h2>
        <p className="muted">Ask role-fit questions and get answers written on the developer's behalf from published evidence.</p>
      </div>
      <div className="recruiter-question-input">
        <textarea
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Are you qualified for a backend new grad role?"
          rows={3}
        />
        <button className="btn" type="button" onClick={askQuestion} disabled={pending || !question.trim()}>
          <Send size={16} /> {pending ? "Checking..." : "Ask"}
        </button>
      </div>
      {error && <p className="muted recruiter-question-error">{error}</p>}
      {answer && (
        <div className="recruiter-answer">
          <div className="recruiter-answer-meta">
            <span className="status">{titleCase(answer.recommendation)}</span>
            <span className="status">{titleCase(answer.confidence)} Confidence</span>
          </div>
          <p>{answer.answer}</p>
          <div className="recruiter-answer-grid">
            <div>
              <h3>Evidence</h3>
              <ul className="analysis-list">
                {answer.evidence.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </div>
            <div>
              <h3>Verify</h3>
              <ul className="analysis-list">
                {answer.verification_questions.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
