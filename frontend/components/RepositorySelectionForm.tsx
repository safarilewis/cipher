"use client";

import { useState } from "react";
import { saveRepositorySelection } from "@/app/actions";
import type { Repository } from "@/lib/types";
import { PendingButton } from "@/components/PendingButton";

export function RepositorySelectionForm({ repositories }: { repositories: Repository[] }) {
  const [selected, setSelected] = useState(() =>
    new Set(repositories.filter((repo) => repo.selected_for_analysis).map((repo) => repo.id))
  );

  function toggle(id: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else if (next.size < 5) {
        next.add(id);
      }
      return next;
    });
  }

  return (
    <form className="repo-selection" action={saveRepositorySelection}>
      {repositories.map((repo) => {
        const checked = selected.has(repo.id);
        const disabled = !checked && selected.size >= 5;
        return (
          <label className={`repo-row${disabled ? " disabled" : ""}`} key={repo.id}>
            <input
              type="checkbox"
              name="repositoryIds"
              value={repo.id}
              checked={checked}
              disabled={disabled}
              onChange={() => toggle(repo.id)}
            />
            <span>
              <strong>{repo.full_name}</strong>
              <small>
                {repo.language ?? "Unknown"} · {repo.commit_count} commits · {repo.stars} stars
                {repo.pushed_at ? ` · pushed ${new Date(repo.pushed_at).toLocaleDateString()}` : ""}
              </small>
              {repo.description && <em>{repo.description}</em>}
            </span>
          </label>
        );
      })}
      <div className="repo-selection-footer">
        <span className="muted">{selected.size}/5 repositories selected</span>
        <PendingButton pendingLabel="Saving repo selection...">Save selected repos</PendingButton>
      </div>
    </form>
  );
}

