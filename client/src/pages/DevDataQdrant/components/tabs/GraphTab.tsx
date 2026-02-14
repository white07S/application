import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph from 'force-graph';
import { Copy, Play, RefreshCw } from 'lucide-react';
import { useAuth } from '../../../../auth/useAuth';
import { qdrantBrowserApi } from '../../api/qdrantBrowserApi';
import { GraphRequest, PointRecord } from '../../types';
import { deduplicatePoints, GraphLink, GraphNode, minimalSpanningTree } from '../../utils/graphHelpers';
import { safeJson } from '../../utils/formatters';
import ErrorState from '../ErrorState';
import EmptyState from '../EmptyState';
import { useQdrantBrowserStore } from '../../store/useQdrantBrowserStore';

interface GraphTabProps {
  collectionName: string;
}

const DEFAULT_GRAPH_REQUEST: GraphRequest = {
  limit: 5,
  tree: false,
};

const GraphTab: React.FC<GraphTabProps> = ({ collectionName }) => {
  const { getApiAccessToken } = useAuth();
  const { graphRequest, setGraphRequest, graphSeedPoint, setGraphSeedPoint, setSelectedPoint } = useQdrantBrowserStore();
  const [requestInput, setRequestInput] = useState(safeJson(graphRequest || DEFAULT_GRAPH_REQUEST));
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; links: GraphLink[] }>({ nodes: [], links: [] });
  const [activePoint, setActivePoint] = useState<PointRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const graphRef = useRef<any>(null);

  useEffect(() => {
    setRequestInput(safeJson(graphRequest || DEFAULT_GRAPH_REQUEST));
  }, [graphRequest]);

  useEffect(() => {
    setSelectedPoint(activePoint);
  }, [activePoint, setSelectedPoint]);

  const expandNode = useCallback(async (node: GraphNode) => {
    try {
      const token = await getApiAccessToken();
      if (!token) {
        return;
      }

      const response = await qdrantBrowserApi.queryPoints(token, collectionName, {
        query: node.id,
        limit: graphRequest.limit || 5,
        with_payload: true,
        with_vector: false,
        filter: graphRequest.filter || undefined,
        using: graphRequest.using || undefined,
      });

      const current = graphRef.current?.graphData?.() || { nodes: [], links: [] };
      const currentNodes = (current.nodes || []) as GraphNode[];
      const currentLinks = (current.links || []) as GraphLink[];
      const incoming = (response.points || []) as GraphNode[];
      const newNodes = deduplicatePoints(currentNodes, incoming);
      const newLinks = incoming.map((point) => ({ source: node.id, target: point.id, score: point.score }));

      const merged = {
        nodes: [...currentNodes, ...newNodes],
        links: [...currentLinks, ...newLinks],
      };

      setGraphData(merged);
      graphRef.current?.graphData(merged);
    } catch (err: any) {
      setError(err?.message || 'Failed to expand graph node');
    }
  }, [collectionName, getApiAccessToken, graphRequest.filter, graphRequest.limit, graphRequest.using]);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }

    if (!graphRef.current) {
      graphRef.current = new ForceGraph(containerRef.current)
        .nodeId('id')
        .nodeLabel((node: any) => `Point ${String(node?.id ?? '')}`)
        .linkLabel((link: any) => (typeof link.score === 'number' ? `score: ${link.score.toFixed(4)}` : ''))
        .nodeColor((node: any) => (node.clicked ? '#e60000' : '#0097cc'))
        .onNodeHover((node: any) => {
          if (!node) {
            setActivePoint(null);
            if (containerRef.current) {
              containerRef.current.style.cursor = 'default';
            }
            return;
          }
          if (containerRef.current) {
            containerRef.current.style.cursor = 'pointer';
          }
          setActivePoint(node);
        })
        .linkDirectionalArrowLength(3)
        .linkDirectionalArrowRelPos(1)
        .d3VelocityDecay(0.2);
      graphRef.current.d3Force('charge')?.strength(-30);
    }

    const onResize = () => {
      if (!graphRef.current || !containerRef.current) {
        return;
      }
      graphRef.current.width(containerRef.current.clientWidth).height(containerRef.current.clientHeight);
    };

    onResize();
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
    };
  }, [collectionName]);

  useEffect(() => {
    if (!graphRef.current) {
      return;
    }

    graphRef.current.onNodeClick((node: any) => {
      node.clicked = true;
      setActivePoint(node);
      expandNode(node as GraphNode);
    });
  }, [expandNode]);

  useEffect(() => {
    if (!graphRef.current) {
      return;
    }
    graphRef.current.graphData(graphData);
  }, [graphData]);

  const runGraph = async (request: GraphRequest, seedPoint?: PointRecord | null) => {
    setLoading(true);
    setError(null);

    try {
      const token = await getApiAccessToken();
      if (!token) {
        return;
      }

      if (request.sample) {
        const matrix = await qdrantBrowserApi.matrixPairs(token, collectionName, {
          sample: request.sample,
          limit: request.limit,
          using: request.using || undefined,
          filter: request.filter || undefined,
        });

        let links = (matrix.pairs || []).map((pair) => ({
          source: pair.a,
          target: pair.b,
          score: pair.score,
        })) as GraphLink[];

        if (request.tree) {
          links = minimalSpanningTree(links, true);
        }

        const uniqueIds = Array.from(new Set(links.flatMap((link) => [link.source, link.target])));
        const retrieved = await qdrantBrowserApi.retrievePoints(token, collectionName, {
          ids: uniqueIds,
          with_payload: true,
          with_vector: false,
        });
        const nodes = (retrieved.points || []) as GraphNode[];
        setGraphData({ nodes, links });
        setLoading(false);
        return;
      }

      const initialNode =
        seedPoint ||
        (
          await qdrantBrowserApi.scrollPoints(token, collectionName, {
            limit: 1,
            with_payload: true,
            with_vector: false,
            filter: request.filter || undefined,
          })
        ).points[0];

      if (!initialNode) {
        setGraphData({ nodes: [], links: [] });
        setError('No points available to initialize the graph');
        setLoading(false);
        return;
      }

      const similar = await qdrantBrowserApi.queryPoints(token, collectionName, {
        query: initialNode.id,
        limit: request.limit || 5,
        with_payload: true,
        with_vector: false,
        filter: request.filter || undefined,
        using: request.using || undefined,
      });

      const initialGraph = {
        nodes: [{ ...(initialNode as GraphNode), clicked: true }, ...(similar.points as GraphNode[])],
        links: (similar.points || []).map((point) => ({
          source: initialNode.id,
          target: point.id,
          score: point.score,
        })),
      };

      setGraphData(initialGraph);
      setActivePoint(initialNode);
      setGraphSeedPoint(null);
    } catch (err: any) {
      setError(err?.message || 'Graph request failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (graphSeedPoint) {
      const seed = graphSeedPoint;
      // Clear the one-shot seed before async work to avoid repeated graph bootstraps on remounts.
      setGraphSeedPoint(null);
      runGraph(graphRequest, seed);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graphSeedPoint]);

  const hasGraph = useMemo(() => graphData.nodes.length > 0, [graphData.nodes.length]);

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-hidden p-3">
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 xl:grid-cols-12">
        <div className="min-h-0 rounded border border-border-light bg-white xl:col-span-8">
          <div className="border-b border-border-light px-3 py-2 text-xs font-semibold text-text-main">Graph Canvas</div>
          <div className="relative h-[calc(100%-33px)]">
            <div ref={containerRef} className="h-full w-full" />
            {loading && (
              <div className="absolute inset-0 flex items-center justify-center bg-white/70 text-xs text-text-main">
                Loading graph...
              </div>
            )}
            {!loading && !hasGraph && !error && (
              <div className="absolute inset-0 p-2">
                <EmptyState title="Run a graph request" description="Use options on the right panel." />
              </div>
            )}
            {error && (
              <div className="absolute left-2 right-2 top-2">
                <ErrorState message={error} />
              </div>
            )}
          </div>
        </div>

        <div className="min-h-0 flex flex-col gap-3 xl:col-span-4">
          <div className="min-h-0 flex-1 rounded border border-border-light bg-white">
            <div className="flex items-center justify-between border-b border-border-light px-3 py-2">
              <div className="text-xs font-semibold text-text-main">Request Editor</div>
              <button
                type="button"
                onClick={() => setRequestInput(safeJson(DEFAULT_GRAPH_REQUEST))}
                className="inline-flex items-center gap-1 rounded border border-border-light bg-white px-2 py-1 text-xs hover:bg-surface-light"
              >
                <RefreshCw size={12} />
                Reset
              </button>
            </div>
            <div className="space-y-2 p-2">
              <textarea
                value={requestInput}
                onChange={(event) => setRequestInput(event.target.value)}
                className="h-52 w-full resize-none rounded border border-border-light p-2 font-mono text-xs focus:outline-none focus:ring-1 focus:ring-primary/35"
              />
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    try {
                      const parsed = JSON.parse(requestInput) as GraphRequest;
                      const normalized: GraphRequest = {
                        limit: parsed.limit || 5,
                        using: parsed.using || null,
                        filter: parsed.filter || null,
                        sample: parsed.sample || null,
                        tree: Boolean(parsed.tree),
                      };
                      setGraphRequest(normalized);
                      runGraph(normalized, null);
                    } catch {
                      setError('Invalid JSON in graph request');
                    }
                  }}
                  className="inline-flex items-center gap-1 rounded border border-border-light bg-white px-2 py-1 text-xs hover:bg-surface-light"
                >
                  <Play size={12} />
                  Run
                </button>
                <button
                  type="button"
                  onClick={() => navigator.clipboard.writeText(requestInput)}
                  className="inline-flex items-center gap-1 rounded border border-border-light bg-white px-2 py-1 text-xs hover:bg-surface-light"
                >
                  <Copy size={12} />
                  Copy
                </button>
              </div>
            </div>
          </div>

          <div className="min-h-0 flex-1 rounded border border-border-light bg-white">
            <div className="border-b border-border-light px-3 py-2 text-xs font-semibold text-text-main">Data Panel</div>
            <pre className="h-[calc(100%-33px)] overflow-auto p-2 text-[11px] text-text-main">
              {activePoint ? safeJson(activePoint) : 'Hover a node to preview point payload'}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
};

export default GraphTab;
