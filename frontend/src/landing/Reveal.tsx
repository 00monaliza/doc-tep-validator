import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

/** Fades a block in when it scrolls into view; still when the system asks for less motion. */
export default function Reveal({ children, className }: { children: ReactNode; className?: string }) {
  const reduce = useReducedMotion();
  if (reduce) return <div className={className}>{children}</div>;
  return (
    <motion.div className={className} initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-10% 0px" }} transition={{ duration: 0.25, ease: "easeOut" }}>
      {children}
    </motion.div>
  );
}
