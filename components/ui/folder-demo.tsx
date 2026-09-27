"use client";

import React, { useState } from "react";
import { Folder } from "./folder";

export const FolderDemo = () => {
  const [color, setColor] = useState<"black" | "white" | "blue">("black");

  return (
    <div className="flex flex-col min-h-screen items-center justify-center bg-neutral-950 p-8 gap-8">
      <div className="flex gap-4">
        {(["black", "white", "blue"] as const).map((c) => (
          <button
            key={c}
            onClick={() => setColor(c)}
            className={`px-4 py-2 rounded-full text-xs font-semibold capitalize border transition-all ${
              color === c
                ? "bg-white text-black border-white"
                : "bg-neutral-900 text-neutral-400 border-neutral-800 hover:border-neutral-600"
            }`}
          >
            {c}
          </button>
        ))}
      </div>
      <div className="h-80 w-96 flex items-center justify-center">
        <Folder color={color} size="md" />
      </div>
    </div>
  );
};

export default FolderDemo;
