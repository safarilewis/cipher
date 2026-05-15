import { LoadingTips } from "@/components/LoadingTips";

export default function SourcesLoading() {
  return (
    <div className="loader-page">
      <LoadingTips label="Checking connected sources" />
    </div>
  );
}
