import { notFound } from "next/navigation";
import type { ComponentType } from "react";
import {
  Award,
  BookOpen,
  BriefcaseBusiness,
  CalendarDays,
  Code2,
  ExternalLink,
  FolderGit2,
  GraduationCap,
  Layers3,
  Sparkles,
  Trophy,
} from "lucide-react";
import { PublicHeader } from "@/components/PublicHeader";
import { PublicProfileQuestionBox } from "@/components/PublicProfileQuestionBox";
import { publicFetch } from "@/lib/public-backend";
import type { Evaluation, ProfileSection, PublicProfile, Repository } from "@/lib/types";

const sectionLabels: Record<ProfileSection["kind"], string> = {
  bootcamp: "Bootcamp",
  certification: "Certification",
  education: "Education",
  experience: "Experience",
  project: "Project",
};

const sectionIcons: Record<ProfileSection["kind"], ComponentType<{ size?: number }>> = {
  bootcamp: GraduationCap,
  certification: Trophy,
  education: GraduationCap,
  experience: BriefcaseBusiness,
  project: BriefcaseBusiness,
};

const languageIconSlugs: Record<string, string> = {
  "c#": "csharp",
  "c++": "cplusplus",
  css: "css3",
  go: "go",
  html: "html5",
  java: "java",
  javascript: "javascript",
  kotlin: "kotlin",
  php: "php",
  python: "python",
  ruby: "ruby",
  rust: "rust",
  scala: "scala",
  shell: "bash",
  swift: "swift",
  typescript: "typescript",
};

type SkillDimension = {
  score?: number | null;
  confidence?: string | null;
  prose?: string | null;
  basis?: string[] | null;
  source?: string | null;
  trend?: string | null;
};

function titleCase(value: string) {
  return value
    .replace(/[_-]/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDate(value: string | null | undefined) {
  if (!value) return "Unknown";
  return new Intl.DateTimeFormat("en", { month: "short", year: "numeric" }).format(new Date(value));
}

function formatDateRange(section: ProfileSection) {
  const start = section.start_date || "No Start";
  const end = section.end_date || "Present";
  return `${start} - ${end}`;
}

function getInitials(name: string) {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "C";
}

function getOverallScore(evaluation: Evaluation | null) {
  const overall = evaluation?.skill_model_v2 && typeof evaluation.skill_model_v2 === "object"
    ? (evaluation.skill_model_v2 as { overall?: { score?: number | null; confidence?: string | null; scope_label?: string | null } }).overall
    : null;

  if (!overall || overall.score == null) {
    return { value: "Unscored", label: "Overall Score", note: "Analysis needs more evidence" };
  }

  return {
    value: `${Math.round(overall.score)}`,
    label: "Overall Score",
    note: `${overall.scope_label ?? "Developer Profile"} - ${titleCase(overall.confidence ?? "unknown")} Confidence`,
  };
}

function getSkillDimensions(evaluation: Evaluation | null) {
  const model = evaluation?.skill_model_v2 && typeof evaluation.skill_model_v2 === "object"
    ? evaluation.skill_model_v2 as Record<string, unknown>
    : {};

  return (["code_quality", "delivery", "algorithms"] as const)
    .map((key) => {
      const raw = model[key];
      if (!raw || typeof raw !== "object") return null;
      const dimension = raw as SkillDimension;
      if (!dimension.prose && !dimension.basis?.length && dimension.score == null) return null;
      return {
        key,
        title: titleCase(key),
        dimension,
      };
    })
    .filter(Boolean) as { key: string; title: string; dimension: SkillDimension }[];
}

function getLanguageStats(repositories: Repository[]) {
  const byLanguage = new Map<string, { count: number; lastUsed: string | null; commits: number }>();

  for (const repository of repositories) {
    if (!repository.language) continue;
    const existing = byLanguage.get(repository.language) ?? { count: 0, lastUsed: null, commits: 0 };
    const lastUsed = !existing.lastUsed || (repository.pushed_at && new Date(repository.pushed_at) > new Date(existing.lastUsed))
      ? repository.pushed_at
      : existing.lastUsed;

    byLanguage.set(repository.language, {
      count: existing.count + 1,
      lastUsed,
      commits: existing.commits + repository.commit_count,
    });
  }

  return [...byLanguage.entries()]
    .map(([language, stats]) => ({ language, ...stats }))
    .sort((left, right) => right.count - left.count || right.commits - left.commits || left.language.localeCompare(right.language));
}

function getLanguageIconUrl(language: string) {
  const slug = languageIconSlugs[language.toLowerCase()];
  return slug ? `https://cdn.jsdelivr.net/gh/devicons/devicon/icons/${slug}/${slug}-original.svg` : null;
}

function LanguageIcon({ language }: { language: string }) {
  const iconUrl = getLanguageIconUrl(language);

  return (
    <div className="public-language-icon" aria-hidden="true">
      {iconUrl ? <img src={iconUrl} alt="" /> : <Code2 size={18} />}
    </div>
  );
}

function SectionCard({ section }: { section: ProfileSection }) {
  const Icon = sectionIcons[section.kind];

  return (
    <article className="public-card">
      <div className="public-card-head">
        <div className="public-icon" aria-hidden="true"><Icon size={18} /></div>
        <div>
          <span className="status">{sectionLabels[section.kind]}</span>
          <h3>{section.title}</h3>
          {section.organization && <p className="muted">{section.organization}</p>}
        </div>
      </div>
      <div className="public-card-meta">
        <CalendarDays size={14} aria-hidden="true" />
        <span>{formatDateRange(section)}</span>
      </div>
      {section.description && <p>{section.description}</p>}
      {section.url && (
        <a className="public-inline-link" href={section.url} target="_blank" rel="noreferrer">
          <ExternalLink size={14} /> Open Reference
        </a>
      )}
    </article>
  );
}

export default async function PublicProfilePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  let profile: PublicProfile;
  try {
    profile = await publicFetch<PublicProfile>(`/public/profiles/${slug}`);
  } catch {
    notFound();
  }

  const displayName = profile.user.name ?? profile.user.slug;
  const selectedRepositories = profile.repositories.filter((repository) => repository.selected_for_analysis);
  const repositoriesForDisplay = selectedRepositories.length > 0 ? selectedRepositories : profile.repositories;
  const totalCommits = profile.repositories.reduce((sum, repository) => sum + repository.commit_count, 0);
  const projectCount = profile.sections.filter((section) => section.kind === "project").length;
  const experienceCount = profile.sections.filter((section) => section.kind === "experience").length;
  const languages = getLanguageStats(profile.repositories);
  const score = getOverallScore(profile.evaluation);
  const skillDimensions = getSkillDimensions(profile.evaluation);
  const reviewedAt = profile.evaluation ? formatDate(profile.evaluation.updated_at) : "Not Reviewed";
  const headline = profile.user.headline ?? profile.evaluation?.summary ?? "Verified developer profile";
  const topRepositories = repositoriesForDisplay
    .slice()
    .sort((left, right) => right.commit_count - left.commit_count || (right.pushed_at ?? "").localeCompare(left.pushed_at ?? ""))
    .slice(0, 6);

  return (
    <>
      <PublicHeader />
      <main className="page public-profile-page">
        <section className="public-hero">
          <div className="public-hero-main">
            <div className="public-identity-row">
              <div className="public-avatar">{getInitials(displayName)}</div>
              <div>
                <span className="status">Verified Developer Profile</span>
                <h1>{displayName}</h1>
                <p className="public-handle">cipher.so/u/{profile.user.slug}</p>
              </div>
            </div>
            <p className="public-headline">{headline}</p>
            <div className="public-pill-row">
              <span className="stack-pill hi">Reviewed {reviewedAt}</span>
              <span className="stack-pill">Projects {projectCount}</span>
              <span className="stack-pill">Experience {experienceCount}</span>
              {profile.leetcode && <span className="stack-pill">LeetCode {profile.leetcode.total_solved}</span>}
            </div>
          </div>
          <div className="public-score-card">
            <Sparkles size={20} aria-hidden="true" />
            <div className="public-score-value">{score.value}</div>
            <div className="public-score-label">{score.label}</div>
            <p>{score.note}</p>
          </div>
        </section>

        <section className="metrics public-metrics">
          <div className="metric"><div className="metric-val g">{totalCommits.toLocaleString()}</div><div className="metric-key">GitHub Commits</div></div>
          <div className="metric"><div className="metric-val">{profile.repositories.length}</div><div className="metric-key">Repositories</div></div>
          <div className="metric"><div className="metric-val">{languages.length}</div><div className="metric-key">Languages</div></div>
          <div className="metric"><div className="metric-val g">{profile.leetcode?.total_solved ?? "N/A"}</div><div className="metric-key">LeetCode Solved</div></div>
        </section>

        {profile.evaluation && (
          <section className="public-section">
            <div className="public-section-head">
              <div>
                <span className="status">Recruiter Summary</span>
                <h2>Hiring Signal</h2>
              </div>
            </div>
            <div className="public-analysis-panel">
              <p>{profile.evaluation.summary}</p>
              {profile.evaluation.recruiter_copy && <div className="analysis-copy">{profile.evaluation.recruiter_copy}</div>}
            </div>
          </section>
        )}

        {skillDimensions.length > 0 && (
          <section className="public-section">
            <div className="public-section-head">
              <div>
                <span className="status">Skills</span>
                <h2>Competence Profile</h2>
              </div>
            </div>
            <div className="public-card-grid">
              {skillDimensions.map(({ key, title, dimension }) => (
                <article className="public-card" key={key}>
                  <div className="public-card-head">
                    <div className="public-icon" aria-hidden="true"><Layers3 size={18} /></div>
                    <div>
                      <span className="status">{titleCase(dimension.confidence ?? "unknown")} Confidence</span>
                      <h3>{title}</h3>
                    </div>
                  </div>
                  <div className="public-skill-score">{typeof dimension.score === "number" ? `${Math.round(dimension.score)}/100` : "Unscored"}</div>
                  {dimension.prose && <p>{dimension.prose}</p>}
                  {!!dimension.basis?.length && (
                    <ul className="analysis-list">
                      {dimension.basis.slice(0, 3).map((item) => <li key={item}>{item}</li>)}
                    </ul>
                  )}
                </article>
              ))}
            </div>
          </section>
        )}

        {languages.length > 0 && (
          <section className="public-section">
            <div className="public-section-head">
              <div>
                <span className="status">GitHub Languages</span>
                <h2>Technology Footprint</h2>
              </div>
            </div>
            <div className="public-language-grid">
              {languages.slice(0, 10).map((language) => (
                <article className="public-language-card" key={language.language}>
                  <LanguageIcon language={language.language} />
                  <div>
                    <h3>{language.language}</h3>
                    <p>{language.count} {language.count === 1 ? "Repository" : "Repositories"}</p>
                    <p className="muted">Last Used {formatDate(language.lastUsed)}</p>
                  </div>
                </article>
              ))}
            </div>
          </section>
        )}

        <section className="public-section">
          <div className="public-section-head">
            <div>
              <span className="status">Ask The Profile</span>
              <h2>Role Fit Questions</h2>
            </div>
          </div>
          <PublicProfileQuestionBox slug={slug} />
        </section>

        <section className="public-section">
          <div className="public-section-head">
            <div>
              <span className="status">Evidence</span>
              <h2>Profile Evidence</h2>
            </div>
          </div>
          <div className="public-card-grid">
            {profile.sections.map((section) => <SectionCard section={section} key={section.id} />)}
          </div>
        </section>

        {topRepositories.length > 0 && (
          <section className="public-section">
            <div className="public-section-head">
              <div>
                <span className="status">GitHub</span>
                <h2>Repository Highlights</h2>
              </div>
            </div>
            <div className="public-card-grid">
              {topRepositories.map((repository) => (
                <article className="public-card" key={repository.id}>
                  <div className="public-card-head">
                    <div className="public-icon" aria-hidden="true"><FolderGit2 size={18} /></div>
                    <div>
                      <span className="status">{repository.language ?? "Repository"}</span>
                      <h3>{repository.full_name}</h3>
                    </div>
                  </div>
                  {repository.description && <p>{repository.description}</p>}
                  <div className="public-card-meta">
                    <span>{repository.commit_count.toLocaleString()} Commits</span>
                    <span>Last Updated {formatDate(repository.pushed_at)}</span>
                  </div>
                </article>
              ))}
            </div>
          </section>
        )}

        <section className="public-section">
          <div className="public-card-grid">
            <article className="public-card">
              <div className="public-card-head">
                <div className="public-icon" aria-hidden="true"><Award size={18} /></div>
                <div>
                  <span className="status">Strengths</span>
                  <h3>Observed Strengths</h3>
                </div>
              </div>
              {!!profile.evaluation?.strengths?.length ? (
                <ul className="analysis-list">
                  {profile.evaluation.strengths.slice(0, 5).map((item) => <li key={item}>{item}</li>)}
                </ul>
              ) : (
                <p className="muted">No reviewed strengths have been published yet.</p>
              )}
            </article>
            <article className="public-card">
              <div className="public-card-head">
                <div className="public-icon" aria-hidden="true"><BookOpen size={18} /></div>
                <div>
                  <span className="status">Growth Areas</span>
                  <h3>Useful Follow-Ups</h3>
                </div>
              </div>
              {!!profile.evaluation?.growth_areas?.length ? (
                <ul className="analysis-list">
                  {profile.evaluation.growth_areas.slice(0, 5).map((item) => <li key={item}>{item}</li>)}
                </ul>
              ) : (
                <p className="muted">No reviewed growth areas have been published yet.</p>
              )}
            </article>
          </div>
        </section>
      </main>
    </>
  );
}
