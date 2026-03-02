import { useEffect } from "react";
import { useChatStore } from "@/store/chatStore";

export function useChat() {
  const store = useChatStore();

  useEffect(() => {
    store.loadConversations();
  }, []);

  return store;
}
