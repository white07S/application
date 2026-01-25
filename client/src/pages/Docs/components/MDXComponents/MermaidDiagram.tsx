import React, { useEffect, useRef, useState } from 'react';
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

export default function MermaidDiagram({ chart }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

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
    <div
      ref={containerRef}
      className="my-4 p-4 bg-surface-alt rounded-lg overflow-x-auto flex justify-center"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}

// Component to detect mermaid code blocks
export function MermaidCodeBlock({ children }: { children: string }) {
  return <MermaidDiagram chart={children} />;
}
