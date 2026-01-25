import { useState, useEffect, useRef } from 'react';
import type { TocHeading } from '../types';

export function useActiveHeading(headings: TocHeading[]): string | null {
  const [activeId, setActiveId] = useState<string | null>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);

  useEffect(() => {
    if (headings.length === 0) return;

    // Clean up previous observer
    if (observerRef.current) {
      observerRef.current.disconnect();
    }

    const headingElements = headings
      .map(h => document.getElementById(h.id))
      .filter((el): el is HTMLElement => el !== null);

    if (headingElements.length === 0) return;

    const callback: IntersectionObserverCallback = (entries) => {
      // Find the first visible heading
      const visibleEntries = entries.filter(entry => entry.isIntersecting);

      if (visibleEntries.length > 0) {
        // Sort by position in document (topmost first)
        visibleEntries.sort((a, b) => {
          const aTop = a.boundingClientRect.top;
          const bTop = b.boundingClientRect.top;
          return aTop - bTop;
        });

        setActiveId(visibleEntries[0].target.id);
      }
    };

    observerRef.current = new IntersectionObserver(callback, {
      rootMargin: '-80px 0px -70% 0px',
      threshold: 0
    });

    headingElements.forEach(el => {
      observerRef.current?.observe(el);
    });

    // Set initial active heading based on scroll position
    const initialActive = headingElements.find(el => {
      const rect = el.getBoundingClientRect();
      return rect.top >= 0 && rect.top < window.innerHeight / 2;
    });

    if (initialActive) {
      setActiveId(initialActive.id);
    } else if (headingElements.length > 0) {
      setActiveId(headingElements[0].id);
    }

    return () => {
      observerRef.current?.disconnect();
    };
  }, [headings]);

  return activeId;
}
