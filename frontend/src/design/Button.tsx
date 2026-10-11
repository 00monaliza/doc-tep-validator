import clsx from "clsx";
import type { ButtonHTMLAttributes } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost"; size?: "sm" | "md" };

const VARIANT = {
  primary: "bg-blue text-sheet border-blue hover:opacity-90",
  secondary: "bg-sheet text-blue border-blue hover:bg-blue-wash",
  ghost: "bg-transparent text-ink-2 border-transparent hover:text-ink hover:bg-sheet",
};

export default function Button({ variant = "secondary", size = "md", type = "button", className, ...rest }: Props) {
  return (
    <button type={type} {...rest} className={clsx(
      "inline-flex items-center gap-1.5 whitespace-nowrap border rounded font-semibold transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed",
      size === "sm" ? "min-h-[26px] px-2.5 text-[13px]" : "min-h-9 px-3.5 text-sm", VARIANT[variant], className)} />
  );
}
