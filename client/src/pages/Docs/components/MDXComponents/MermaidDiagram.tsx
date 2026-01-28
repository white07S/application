import React, { useEffect, useRef, useState, useCallback } from 'react';
import mermaid from 'mermaid';

interface MermaidDiagramProps {
  chart: string;
}

// Initialize mermaid with light theme
mermaid.initialize({
  startOnLoad: false,
  theme: 'base',
  themeVariables: {
    primaryColor: '#e60000',
    primaryTextColor: '#1c1c1c',
    primaryBorderColor: '#e60000',
    lineColor: '#4b5563',
    secondaryColor: '#008e97',
    tertiaryColor: '#f9f9f7',
    background: '#ffffff',
    mainBkg: '#f9f9f7',
    nodeBorder: '#d1d5db',
    clusterBkg: '#f3f4f6',
    titleColor: '#1c1c1c',
    edgeLabelBackground: '#ffffff',
    actorBkg: '#f9f9f7',
    actorBorder: '#d1d5db',
    actorTextColor: '#1c1c1c',
    signalColor: '#4b5563',
    signalTextColor: '#1c1c1c',
    labelTextColor: '#1c1c1c',
    noteBkgColor: '#f9f9f7',
    noteTextColor: '#1c1c1c',
    noteBorderColor: '#d1d5db'
  },
  flowchart: {
    curve: 'basis',
    padding: 20
  },
  securityLevel: 'loose'
});

// Zoom Modal Component
function DiagramZoomModal({
  svg,
  isOpen,
  onClose
}: {
  svg: string;
  isOpen: boolean;
  onClose: () => void;
}) {
  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const containerRef = useRef<HTMLDivElement>(null);

  // Reset zoom and position when modal opens
  useEffect(() => {
    if (isOpen) {
      setScale(1);
      setPosition({ x: 0, y: 0 });
    }
  }, [isOpen]);

  // Handle keyboard events
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      } else if (e.key === '+' || e.key === '=') {
        setScale((s) => Math.min(s + 0.25, 4));
      } else if (e.key === '-') {
        setScale((s) => Math.max(s - 0.25, 0.25));
      } else if (e.key === '0') {
        setScale(1);
        setPosition({ x: 0, y: 0 });
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.1 : 0.1;
    setScale((s) => Math.max(0.25, Math.min(4, s + delta)));
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button === 0) {
      setIsDragging(true);
      setDragStart({ x: e.clientX - position.x, y: e.clientY - position.y });
    }
  }, [position]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (isDragging) {
      setPosition({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y
      });
    }
  }, [isDragging, dragStart]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal Content */}
      <div className="relative w-full h-full flex flex-col">
        {/* Header with controls */}
        <div className="absolute top-0 left-0 right-0 z-10 flex items-center justify-between p-4 bg-gradient-to-b from-black/50 to-transparent">
          <div className="flex items-center gap-2">
            <span className="text-white/70 text-sm font-medium">
              Diagram Viewer
            </span>
            <span className="text-white/50 text-xs">
              (Scroll to zoom, drag to pan)
            </span>
          </div>

          <div className="flex items-center gap-2">
            {/* Zoom controls */}
            <div className="flex items-center gap-1 bg-white/10 rounded-lg p-1">
              <button
                onClick={() => setScale((s) => Math.max(s - 0.25, 0.25))}
                className="p-2 text-white/70 hover:text-white hover:bg-white/10 rounded transition-colors"
                title="Zoom out (-)"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
                </svg>
              </button>
              <span className="text-white text-sm font-mono px-2 min-w-[4rem] text-center">
                {Math.round(scale * 100)}%
              </span>
              <button
                onClick={() => setScale((s) => Math.min(s + 0.25, 4))}
                className="p-2 text-white/70 hover:text-white hover:bg-white/10 rounded transition-colors"
                title="Zoom in (+)"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
              </button>
              <button
                onClick={() => {
                  setScale(1);
                  setPosition({ x: 0, y: 0 });
                }}
                className="p-2 text-white/70 hover:text-white hover:bg-white/10 rounded transition-colors"
                title="Reset (0)"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </button>
            </div>

            {/* Close button */}
            <button
              onClick={onClose}
              className="p-2 text-white/70 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
              title="Close (Esc)"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Diagram container */}
        <div
          ref={containerRef}
          className="flex-1 overflow-hidden cursor-grab active:cursor-grabbing"
          onWheel={handleWheel}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
        >
          <div
            className="w-full h-full flex items-center justify-center"
            style={{
              transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
              transformOrigin: 'center center',
              transition: isDragging ? 'none' : 'transform 0.1s ease-out'
            }}
          >
            <div
              className="bg-white rounded-lg p-8 shadow-2xl"
              dangerouslySetInnerHTML={{ __html: svg }}
            />
          </div>
        </div>

        {/* Keyboard shortcuts hint */}
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-4 text-white/50 text-xs">
          <span><kbd className="px-1.5 py-0.5 bg-white/10 rounded">+</kbd> / <kbd className="px-1.5 py-0.5 bg-white/10 rounded">-</kbd> Zoom</span>
          <span><kbd className="px-1.5 py-0.5 bg-white/10 rounded">0</kbd> Reset</span>
          <span><kbd className="px-1.5 py-0.5 bg-white/10 rounded">Esc</kbd> Close</span>
        </div>
      </div>
    </div>
  );
}

export default function MermaidDiagram({ chart }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [isZoomOpen, setIsZoomOpen] = useState(false);

  useEffect(() => {
    async function renderDiagram() {
      if (!chart.trim()) return;

      try {
        const id = `mermaid-${Math.random().toString(36).substring(7)}`;
        const { svg: renderedSvg } = await mermaid.render(id, chart.trim());
        setSvg(renderedSvg);
        setError(null);
      } catch (err) {
        console.error('Mermaid rendering error:', err);
        setError('Failed to render diagram');
      }
    }

    renderDiagram();
  }, [chart]);

  if (error) {
    return (
      <div className="my-4 p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
        <p className="text-red-400 text-sm">{error}</p>
        <pre className="mt-2 text-xs text-text-tertiary overflow-x-auto">
          {chart}
        </pre>
      </div>
    );
  }

  return (
    <>
      <div className="my-4 relative group">
        {/* Zoom button */}
        <button
          onClick={() => setIsZoomOpen(true)}
          className="absolute top-2 right-2 z-10 p-2 bg-surface-primary/90 hover:bg-surface-primary border border-border-primary rounded-lg shadow-sm opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1.5 text-text-secondary hover:text-text-primary"
          title="Click to zoom"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
          </svg>
          <span className="text-xs font-medium">Zoom</span>
        </button>

        {/* Diagram container */}
        <div
          ref={containerRef}
          className="p-4 bg-surface-alt rounded-lg overflow-x-auto flex justify-center cursor-pointer hover:ring-2 hover:ring-primary/20 transition-shadow"
          onClick={() => setIsZoomOpen(true)}
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      </div>

      {/* Zoom Modal */}
      <DiagramZoomModal
        svg={svg}
        isOpen={isZoomOpen}
        onClose={() => setIsZoomOpen(false)}
      />
    </>
  );
}

// Component to detect mermaid code blocks
export function MermaidCodeBlock({ children }: { children: string }) {
  return <MermaidDiagram chart={children} />;
}
