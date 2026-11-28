'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

function ChatIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M7.5 19.5 4 21l1.2-3.6A8.5 8.5 0 1 1 12 20.5a8.4 8.4 0 0 1-4.5-1"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function DocumentsIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M7 3.75h7.2L19 8.6V20.25H7V3.75Z"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinejoin="round"
      />
      <path
        d="M14 3.75V9h5.2M9.5 13h6M9.5 16.5h6"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ApprovalsIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M9 11.5 11 13.5 15.5 9"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z"
        stroke="currentColor"
        strokeWidth="1.75"
      />
    </svg>
  );
}

function EvalsIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M4 20h16M7 16v-4M12 16V7M17 16v-6"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
      />
    </svg>
  );
}

function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none">
        <path
          d="M12 3.5 19 7.5v9l-7 4-7-4v-9l7-4Z"
          stroke="currentColor"
          strokeWidth="1.75"
          strokeLinejoin="round"
        />
        <path
          d="M12 12v8.5M12 12 5 8M12 12l7-4"
          stroke="currentColor"
          strokeWidth="1.75"
          strokeLinecap="round"
        />
      </svg>
    </span>
  );
}

const links = [
  { href: '/', label: 'Chat', icon: ChatIcon },
  { href: '/documents', label: 'Documents', icon: DocumentsIcon },
  { href: '/approvals', label: 'Approvals', icon: ApprovalsIcon },
  { href: '/evals', label: 'Evals', icon: EvalsIcon },
] as const;

export function SiteHeader() {
  const pathname = usePathname();

  return (
    <header className="site-header">
      <Link href="/" className="brand">
        <BrandMark />
        <span className="brand-text">Support Desk</span>
      </Link>
      <nav className="site-nav" aria-label="Primary">
        {links.map(({ href, label, icon: Icon }) => {
          const current =
            href === '/' ? pathname === '/' : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className="nav-link"
              aria-current={current ? 'page' : undefined}
            >
              <Icon />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
