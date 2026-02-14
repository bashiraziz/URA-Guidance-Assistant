import ChatWidget from "@/components/chat-widget";
import { requireServerSession } from "@/lib/auth";

export default async function ProtectedLayout({ children }: { children: React.ReactNode }) {
  await requireServerSession();
  return (
    <>
      {children}
      <ChatWidget />
    </>
  );
}
