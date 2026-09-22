/* Shared motion primitives — the animation vocabulary of the console.
   All pages/components import these so entrances, staggers and micro-interactions
   feel like one coherent product. */

import { motion } from 'motion/react';
import type { Variants } from 'motion/react';
import type { CSSProperties, ReactNode } from 'react';

/** Signature ease — soft, confident, slightly snappy. */
export const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

export const springSoft = { type: 'spring', stiffness: 320, damping: 30 } as const;
export const springSnappy = { type: 'spring', stiffness: 480, damping: 34 } as const;

/** Page-level transition wrapper. Used inside AnimatePresence route switches. */
export function Page({ children, className = 'page', style }: { children: ReactNode; className?: string; style?: CSSProperties }) {
  return (
    <motion.div
      className={className}
      style={style}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -12 }}
      transition={{ duration: 0.32, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}

export const staggerParent: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.055, delayChildren: 0.05 } },
};

export const staggerChild: Variants = {
  hidden: { opacity: 0, y: 18 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE } },
};

/** Staggered list container — children should be <Item>. */
export function Stagger({ children, className, style }: { children: ReactNode; className?: string; style?: CSSProperties }) {
  return (
    <motion.div className={className} style={style} variants={staggerParent} initial="hidden" animate="show">
      {children}
    </motion.div>
  );
}

/** Staggered list item. */
export function Item({
  children,
  className,
  style,
  onClick,
  role,
  tabIndex,
  onKeyDown,
}: {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  onClick?: () => void;
  role?: string;
  tabIndex?: number;
  onKeyDown?: (e: React.KeyboardEvent) => void;
}) {
  return (
    <motion.div
      className={className}
      style={style}
      variants={staggerChild}
      onClick={onClick}
      role={role}
      tabIndex={tabIndex}
      onKeyDown={onKeyDown}
    >
      {children}
    </motion.div>
  );
}

/** Simple fade-up reveal for one-off blocks (banners, sections). */
export function FadeIn({
  children,
  className,
  style,
  delay = 0,
  y = 14,
}: {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  delay?: number;
  y?: number;
}) {
  return (
    <motion.div
      className={className}
      style={style}
      initial={{ opacity: 0, y }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: EASE, delay }}
    >
      {children}
    </motion.div>
  );
}

/** Reveal on scroll into view — for long pages (auditor, export manifest). */
export function Reveal({ children, className, style }: { children: ReactNode; className?: string; style?: CSSProperties }) {
  return (
    <motion.div
      className={className}
      style={style}
      initial={{ opacity: 0, y: 22 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{ duration: 0.5, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}

/** Hover-lift card wrapper — springy translate + shadow handled by CSS class. */
export function Lift({
  children,
  className,
  onClick,
  role,
  tabIndex,
  onKeyDown,
}: {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
  role?: string;
  tabIndex?: number;
  onKeyDown?: (e: React.KeyboardEvent) => void;
}) {
  return (
    <motion.div
      className={className}
      onClick={onClick}
      role={role}
      tabIndex={tabIndex}
      onKeyDown={onKeyDown}
      whileHover={{ y: -4 }}
      whileTap={{ scale: 0.99 }}
      transition={springSnappy}
    >
      {children}
    </motion.div>
  );
}
