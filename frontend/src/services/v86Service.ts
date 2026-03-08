/**
 * v86 Service — Singleton wrapper around the v86 x86 emulator.
 *
 * Provides boot/shutdown lifecycle, programmatic command execution
 * via serial0, and raw output streaming for xterm.js.
 */

// v86 is loaded as a global script from /v86/libv86.js
declare class V86 {
    constructor(options: Record<string, unknown>);
    add_listener(event: string, callback: (data: unknown) => void): void;
    serial0_send(data: string): void;
    destroy(): void;
    is_running(): boolean;
}

export type OutputCallback = (char: string) => void;

class V86Service {
    private emulator: V86 | null = null;
    private outputListeners: Set<OutputCallback> = new Set();
    private _isReady = false;
    private _isBooting = false;
    private bootPromiseResolve: (() => void) | null = null;
    private outputBuffer = "";

    get isReady() {
        return this._isReady;
    }
    get isBooting() {
        return this._isBooting;
    }

    /** Load the v86 script if not already present */
    private loadScript(): Promise<void> {
        return new Promise((resolve, reject) => {
            if ((window as unknown as Record<string, unknown>).V86) {
                resolve();
                return;
            }
            const script = document.createElement("script");
            script.src = "/v86/libv86.js";
            script.onload = () => resolve();
            script.onerror = () => reject(new Error("Failed to load v86 engine"));
            document.head.appendChild(script);
        });
    }

    /** Boot the Alpine Linux VM */
    async boot(): Promise<void> {
        if (this.emulator || this._isBooting) return;

        this._isBooting = true;

        await this.loadScript();

        const V86Constructor = (window as unknown as Record<string, typeof V86>).V86;

        return new Promise<void>((resolve) => {
            this.bootPromiseResolve = resolve;

            this.emulator = new V86Constructor({
                wasm_path: "/v86/v86.wasm",
                bios: { url: "/v86/seabios.bin" },
                vga_bios: { url: "/v86/vgabios.bin" },
                cdrom: { url: "/v86/alpine.iso" },
                memory_size: 128 * 1024 * 1024,   // 128 MB RAM
                vga_memory_size: 2 * 1024 * 1024,  // 2 MB VGA
                autostart: true,
                disable_keyboard: true,
                disable_mouse: true,
                disable_speaker: true,
                // No screen_container — we use serial only
            });

            // Listen for serial output
            this.emulator!.add_listener("serial0-output-byte", (byte: unknown) => {
                const char = String.fromCharCode(byte as number);
                this.outputBuffer += char;

                // Notify all listeners (xterm.js, etc.)
                for (const cb of this.outputListeners) {
                    cb(char);
                }

                // Detect login prompt -> auto-login as root
                if (!this._isReady && this.outputBuffer.includes("login:")) {
                    this.outputBuffer = "";
                    setTimeout(() => {
                        this.emulator?.serial0_send("root\n");
                    }, 500);
                }

                // Detect that shell is ready (prompt after login)
                if (!this._isReady && this.outputBuffer.includes("localhost:~#")) {
                    this._isReady = true;
                    this._isBooting = false;
                    this.outputBuffer = "";
                    this.bootPromiseResolve?.();
                    this.bootPromiseResolve = null;
                }
            });

            // Timeout: resolve anyway after 30 seconds
            setTimeout(() => {
                if (this._isBooting) {
                    this._isBooting = false;
                    this._isReady = true;
                    this.bootPromiseResolve?.();
                    this.bootPromiseResolve = null;
                }
            }, 30000);
        });
    }

    /** Shutdown the VM */
    shutdown(): void {
        if (this.emulator) {
            this.emulator.destroy();
            this.emulator = null;
        }
        this._isReady = false;
        this._isBooting = false;
        this.outputBuffer = "";
        this.outputListeners.clear();
    }

    /** Register a callback for raw serial output characters */
    onOutput(cb: OutputCallback): () => void {
        this.outputListeners.add(cb);
        return () => this.outputListeners.delete(cb);
    }

    /** Send raw input to the VM serial port (for direct user typing) */
    sendInput(data: string): void {
        if (this.emulator && this._isReady) {
            this.emulator.serial0_send(data);
        }
    }

    /**
     * Execute a shell command and return the output.
     * Used by the LLM tool bridge.
     */
    executeCommand(command: string): Promise<string> {
        return new Promise((resolve) => {
            if (!this.emulator || !this._isReady) {
                resolve("[ERROR] VM is not running or not ready.");
                return;
            }

            let output = "";
            let capturing = false;
            const marker = `__CMD_DONE_${Date.now()}__`;

            const handler = (char: string) => {
                output += char;

                // We inject a marker after the command to detect completion
                if (output.includes(marker)) {
                    this.outputListeners.delete(handler);

                    // Extract the output between the command echo and the marker
                    const parts = output.split(marker);
                    let result = parts[0] || "";

                    // Remove the echoed command line from the beginning
                    const lines = result.split("\n");
                    // First line is the echoed command, last line might be the prompt
                    if (lines.length > 1) {
                        result = lines.slice(1).join("\n");
                    }
                    // Remove trailing prompt
                    result = result.replace(/\n?localhost[^#]*#\s*$/, "").trim();

                    resolve(result);
                }
            };

            this.outputListeners.add(handler);

            // Send the command followed by an echo of the marker
            this.emulator.serial0_send(`${command}; echo "${marker}"\n`);

            // Timeout after 15 seconds
            setTimeout(() => {
                this.outputListeners.delete(handler);
                if (output) {
                    resolve(output.trim());
                } else {
                    resolve("[TIMEOUT] Command did not complete within 15 seconds.");
                }
            }, 15000);
        });
    }
}

// Singleton
export const v86Service = new V86Service();
