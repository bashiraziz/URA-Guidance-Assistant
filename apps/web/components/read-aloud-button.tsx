"use client";

import { useCallback, useEffect, useRef, useState } from "react";

function stripMarkdown(md: string): string {
  return md
    .replace(/```[\s\S]*?```/g, "")        // code blocks
    .replace(/`([^`]+)`/g, "$1")            // inline code
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, "") // images
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1") // links
    .replace(/^#{1,6}\s+/gm, "")            // headings
    .replace(/(\*{1,2}|_{1,2})(.*?)\1/g, "$2") // bold/italic
    .replace(/~~(.*?)~~/g, "$1")            // strikethrough
    .replace(/^[-*+]\s+/gm, "")            // unordered lists
    .replace(/^\d+\.\s+/gm, "")            // ordered lists
    .replace(/^>\s+/gm, "")                // blockquotes
    .replace(/---+/g, "")                  // horizontal rules
    .replace(/\|/g, " ")                   // table pipes
    .replace(/\n{2,}/g, "\n")
    .trim();
}

type Props = {
  text: string;
};

export default function ReadAloudButton({ text }: Props) {
  const [state, setState] = useState<"idle" | "speaking" | "paused">("idle");
  const [supported, setSupported] = useState(false);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  useEffect(() => {
    setSupported(typeof window !== "undefined" && "speechSynthesis" in window);
  }, []);

  // Cancel on unmount
  useEffect(() => {
    return () => {
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  const speak = useCallback(() => {
    if (!supported) return;
    const synth = window.speechSynthesis;

    if (state === "speaking") {
      synth.pause();
      setState("paused");
      return;
    }

    if (state === "paused") {
      synth.resume();
      setState("speaking");
      return;
    }

    // idle → start new
    synth.cancel();
    const plain = stripMarkdown(text);
    if (!plain) return;

    const utt = new SpeechSynthesisUtterance(plain);
    const voices = synth.getVoices();
    const enVoice = voices.find((v) => v.lang.startsWith("en"));
    if (enVoice) utt.voice = enVoice;
    utt.lang = "en-US";

    utt.onend = () => setState("idle");
    utt.onerror = () => setState("idle");

    utteranceRef.current = utt;
    synth.speak(utt);
    setState("speaking");
  }, [state, supported, text]);

  const stop = useCallback(() => {
    if (!supported) return;
    window.speechSynthesis.cancel();
    setState("idle");
  }, [supported]);

  if (!supported) return null;

  return (
    <span className="read-aloud-group">
      <button
        type="button"
        className={`read-aloud-btn${state === "speaking" ? " speaking" : ""}`}
        onClick={speak}
        title={state === "idle" ? "Read aloud" : state === "speaking" ? "Pause" : "Resume"}
      >
        {state === "idle" ? "\u25B6" : state === "speaking" ? "\u23F8" : "\u25B6"}
      </button>
      {state !== "idle" && (
        <button
          type="button"
          className="read-aloud-btn"
          onClick={stop}
          title="Stop"
        >
          {"\u23F9"}
        </button>
      )}
    </span>
  );
}
