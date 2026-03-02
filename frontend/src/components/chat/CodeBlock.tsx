import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import { CopyButton } from "@/components/common";

const languageNames: Record<string, string> = {
  js: "JavaScript",
  jsx: "JavaScript (JSX)",
  ts: "TypeScript",
  tsx: "TypeScript (TSX)",
  py: "Python",
  rb: "Ruby",
  rs: "Rust",
  go: "Go",
  java: "Java",
  cpp: "C++",
  c: "C",
  cs: "C#",
  sh: "Shell",
  bash: "Bash",
  zsh: "Zsh",
  sql: "SQL",
  json: "JSON",
  yaml: "YAML",
  yml: "YAML",
  html: "HTML",
  css: "CSS",
  md: "Markdown",
  xml: "XML",
  toml: "TOML",
  dockerfile: "Dockerfile",
};

interface CodeBlockProps {
  language: string | undefined;
  code: string;
}

const customStyle: React.CSSProperties = {
  margin: 0,
  borderRadius: 0,
  background: "#0a0a0f",
  fontSize: "13px",
};

export function CodeBlock({ language, code }: CodeBlockProps) {
  const displayName =
    (language && languageNames[language]) || language || "Code";

  return (
    <div className="rounded-lg border border-gray-700/50 overflow-hidden my-3">
      <div className="flex items-center justify-between bg-gray-800/80 px-3 py-1.5 text-xs text-gray-400">
        <span>{displayName}</span>
        <CopyButton text={code} size="sm" />
      </div>
      <SyntaxHighlighter
        style={vscDarkPlus}
        language={language || "text"}
        customStyle={customStyle}
        wrapLongLines
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}
