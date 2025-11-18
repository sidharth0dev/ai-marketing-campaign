import * as React from "react"

import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "file:text-white file:bg-gray-700 file:px-3 file:py-1.5 file:rounded-md file:border-0 file:font-medium file:text-sm placeholder:text-gray-400 selection:bg-primary selection:text-primary-foreground border-white/20 h-10 w-full min-w-0 rounded-md border bg-slate-900/40 px-3 py-2 text-base text-gray-100 shadow-xs transition-[color,box-shadow] outline-none disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 md:text-sm",
        "focus-visible:border-white/60 focus-visible:ring-white/30 focus-visible:ring-[3px]",
        "aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive",
        className
      )}
      {...props}
    />
  )
}

export { Input }
