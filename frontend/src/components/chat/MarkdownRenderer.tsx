import { memo } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";
import { CodeBlock } from "./CodeBlock";

const remarkPlugins = [remarkGfm];

const components: Components = {
  code({ className, children }) {
    const match = className?.match(/^language-(\w+)/);
    const code = String(children).replace(/\n$/, "");

    if (match) {
      return <CodeBlock language={match[1]} code={code} />;
    }

    return (
      <code className="bg-gray-700/60 rounded px-1.5 py-0.5 text-[13px]">
        {children}
      </code>
    );
  },
  pre({ children }) {
    return <>{children}</>;
  },
  table({ children }) {
    return (
      <div className="overflow-x-auto my-3">
        <table className="min-w-full border border-gray-700/50 text-sm">
          {children}
        </table>
      </div>
    );
  },
  th({ children }) {
    return (
      <th className="border border-gray-700/50 bg-gray-800/60 px-3 py-1.5 text-left font-medium text-gray-300">
        {children}
      </th>
    );
  },
  td({ children }) {
    return (
      <td className="border border-gray-700/50 px-3 py-1.5 text-gray-300">
        {children}
      </td>
    );
  },
};

interface MarkdownRendererProps {
  content: string;
}

export const MarkdownRenderer = memo(function MarkdownRenderer({
  content,
}: MarkdownRendererProps) {
  return (
    <div className="prose prose-invert prose-sm max-w-none">
      <Markdown remarkPlugins={remarkPlugins} components={components}>
        {content}
      </Markdown>
    </div>
  );
});
