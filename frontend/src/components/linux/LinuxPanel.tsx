import { useEffect, useRef } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import { useLinuxStore } from "@/store/linuxStore";
import { v86Service } from "@/services/v86Service";

export function LinuxPanel() {
    const { isVMBooting, isVMReady, shutdownVM } = useLinuxStore();
    const termRef = useRef<HTMLDivElement>(null);
    const terminalRef = useRef<Terminal | null>(null);
    const fitAddonRef = useRef<FitAddon | null>(null);

    useEffect(() => {
        if (!termRef.current || terminalRef.current) return;

        const term = new Terminal({
            cursorBlink: true,
            fontSize: 13,
            fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
            theme: {
                background: "#0d1117",
                foreground: "#c9d1d9",
                cursor: "#58a6ff",
                cursorAccent: "#0d1117",
                selectionBackground: "#264f78",
                black: "#0d1117",
                red: "#ff7b72",
                green: "#3fb950",
                yellow: "#d29922",
                blue: "#58a6ff",
                magenta: "#bc8cff",
                cyan: "#39d353",
                white: "#c9d1d9",
                brightBlack: "#484f58",
                brightRed: "#ffa198",
                brightGreen: "#56d364",
                brightYellow: "#e3b341",
                brightBlue: "#79c0ff",
                brightMagenta: "#d2a8ff",
                brightCyan: "#56d364",
                brightWhite: "#f0f6fc",
            },
        });

        const fitAddon = new FitAddon();
        term.loadAddon(fitAddon);
        term.open(termRef.current);
        fitAddon.fit();

        terminalRef.current = term;
        fitAddonRef.current = fitAddon;

        // Stream v86 serial output to xterm.js
        const unsubscribe = v86Service.onOutput((char) => {
            term.write(char);
        });

        // Forward user keystrokes to v86
        term.onData((data) => {
            v86Service.sendInput(data);
        });

        // Handle resize
        const resizeObserver = new ResizeObserver(() => {
            fitAddon.fit();
        });
        resizeObserver.observe(termRef.current);

        return () => {
            unsubscribe();
            resizeObserver.disconnect();
            term.dispose();
            terminalRef.current = null;
            fitAddonRef.current = null;
        };
    }, []);

    return (
        <div className="flex flex-col h-full bg-[#0d1117] border-l border-gray-800">
            {/* Header */}
            <div className="flex items-center justify-between px-3 py-2 bg-gray-900/80 border-b border-gray-800">
                <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-gray-300">
                        🐧 Alpine Linux
                    </span>
                    {isVMBooting && (
                        <span className="flex items-center gap-1.5 text-xs text-amber-400">
                            <svg className="w-3 h-3 animate-spin" viewBox="0 0 24 24" fill="none">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                            </svg>
                            Booting...
                        </span>
                    )}
                    {isVMReady && (
                        <span className="flex items-center gap-1 text-xs text-green-400">
                            <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                            Ready
                        </span>
                    )}
                </div>
                <button
                    onClick={shutdownVM}
                    className="px-2 py-0.5 text-xs text-red-400 hover:text-red-300 hover:bg-red-900/30 rounded transition-colors"
                    title="Shutdown VM"
                >
                    ⏻ Stop
                </button>
            </div>

            {/* Terminal */}
            <div ref={termRef} className="flex-1 p-1" />
        </div>
    );
}
