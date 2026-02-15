import ChatWidget from "@/components/chat-widget";

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      {children}
      <ChatWidget />
    </>
  );
}
