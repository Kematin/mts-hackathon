import { ThreadList } from "@/components/assistant-ui/thread-list";

export default function ThreadWindow() {
  return (
    <div className="grid h-full grid-cols-[200px_1fr]">
      <ThreadList />
    </div>
  );
}