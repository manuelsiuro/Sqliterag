import { useState, useEffect } from "react";
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
  const [isPreview, setIsPreview] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const displayName =
    (language && languageNames[language]) || language || "Code";
  const isHtml = language === "html";

  // Listen for errors posted from the iframe
  useEffect(() => {
    if (!isPreview) {
      setPreviewError(null);
      return;
    }

    const handleMessage = (event: MessageEvent) => {
      if (event.data?.type === 'IFRAME_ERROR') {
        setPreviewError(event.data.message);
      }
    };

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [isPreview]);

  // Inject a script into the raw HTML to catch errors and forward them
  const getInjectedCode = () => {
    if (!isHtml) return code;

    const errorCatcherScript = `
      <script>
        window.onerror = function(message, source, lineno, colno, error) {
          window.parent.postMessage({ type: 'IFRAME_ERROR', message: message + ' (Line ' + lineno + ')' }, '*');
          return true;
        };
        const originalConsoleError = console.error;
        console.error = function(...args) {
          window.parent.postMessage({ type: 'IFRAME_ERROR', message: args.join(' ') }, '*');
          originalConsoleError.apply(console, args);
        };
      </script>
    `;

    // Attempt to inject right after <head>, else prepend
    if (code.includes('<head>')) {
      return code.replace('<head>', '<head>' + errorCatcherScript);
    }
    return errorCatcherScript + code;
  };

  return (
    <div className="rounded-lg border border-gray-700/50 overflow-hidden my-3">
      <div className="flex items-center justify-between bg-gray-800/80 px-3 py-1.5 text-xs text-gray-400">
        <div className="flex items-center gap-3">
          <span>{displayName}</span>
          {isHtml && (
            <button
              onClick={() => setIsPreview(!isPreview)}
              className={`px-2 py-0.5 rounded transition-colors ${isPreview
                ? "bg-purple-600/80 text-white font-medium"
                : "bg-gray-700 hover:bg-gray-600"
                }`}
            >
              {isPreview ? "Code" : "Preview"}
            </button>
          )}
        </div>
        <CopyButton text={code} size="sm" />
      </div>
      {previewError && isPreview && (
        <div className="bg-red-900/50 text-red-200 text-xs px-3 py-2 border-b border-red-800 flex justify-between items-center">
          <span className="font-mono truncate mr-2">Error: {previewError}</span>
          <button onClick={() => setPreviewError(null)} className="text-red-400 hover:text-white">&times;</button>
        </div>
      )}
      {isPreview ? (
        <iframe
          srcDoc={getInjectedCode()}
          sandbox="allow-scripts"
          className="w-full h-[500px] border-none bg-white"
          title="HTML Preview"
        />
      ) : (
        <SyntaxHighlighter
          style={vscDarkPlus}
          language={language || "text"}
          customStyle={customStyle}
          wrapLongLines
        >
          {code}
        </SyntaxHighlighter>
      )}
    </div>
  );
}
