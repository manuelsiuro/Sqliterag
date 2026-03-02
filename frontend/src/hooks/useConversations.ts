import { useEffect } from "react";
import { useChatStore } from "@/store/chatStore";

export function useConversations() {
  const { conversations, loadConversations, createConversation, deleteConversation } =
    useChatStore();

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  return { conversations, createConversation, deleteConversation, refresh: loadConversations };
}
