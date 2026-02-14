import { PointRecord } from '../types';

export interface GraphNode extends PointRecord {
  id: string | number;
  clicked?: boolean;
}

export interface GraphLink {
  source: string | number;
  target: string | number;
  score?: number;
}

export function deduplicatePoints(existing: GraphNode[], incoming: GraphNode[]): GraphNode[] {
  const existingIds = new Set(existing.map((item) => String(item.id)));
  return incoming.filter((item) => !existingIds.has(String(item.id)));
}

export function minimalSpanningTree(links: GraphLink[], descending = true): GraphLink[] {
  const sortedLinks = [...links].sort((a, b) =>
    descending ? (b.score || 0) - (a.score || 0) : (a.score || 0) - (b.score || 0)
  );

  const parent: Record<string, string> = {};
  const rank: Record<string, number> = {};

  const findRoot = (item: string): string => {
    if (parent[item] === item) {
      return item;
    }
    parent[item] = findRoot(parent[item]);
    return parent[item];
  };

  const union = (left: string, right: string): void => {
    const leftRoot = findRoot(left);
    const rightRoot = findRoot(right);
    if (leftRoot === rightRoot) {
      return;
    }
    if ((rank[leftRoot] || 0) < (rank[rightRoot] || 0)) {
      parent[leftRoot] = rightRoot;
      return;
    }
    if ((rank[leftRoot] || 0) > (rank[rightRoot] || 0)) {
      parent[rightRoot] = leftRoot;
      return;
    }
    parent[rightRoot] = leftRoot;
    rank[leftRoot] = (rank[leftRoot] || 0) + 1;
  };

  sortedLinks.forEach((link) => {
    const source = String(link.source);
    const target = String(link.target);
    if (!(source in parent)) {
      parent[source] = source;
      rank[source] = 0;
    }
    if (!(target in parent)) {
      parent[target] = target;
      rank[target] = 0;
    }
  });

  const selected: GraphLink[] = [];
  sortedLinks.forEach((link) => {
    const source = String(link.source);
    const target = String(link.target);
    if (findRoot(source) !== findRoot(target)) {
      selected.push(link);
      union(source, target);
    }
  });

  return selected;
}

