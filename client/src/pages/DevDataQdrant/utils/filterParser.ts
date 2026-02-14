import { ParsedFilter, PayloadSchemaEntry, PointId } from '../types';

export function isSameFilter(a: ParsedFilter, b: ParsedFilter): boolean {
  return a.key === b.key && a.value === b.value && Boolean(a.isIdFilter) === Boolean(b.isIdFilter);
}

export function uniqFilters(filters: ParsedFilter[]): ParsedFilter[] {
  return filters.filter((item, index) => filters.findIndex((candidate) => isSameFilter(candidate, item)) === index);
}

function parseIdValue(rawValue: string): PointId {
  const numberValue = Number(rawValue);
  if (!Number.isNaN(numberValue) && Number.isInteger(numberValue)) {
    return numberValue;
  }
  return rawValue;
}

function normalizeBySchema(
  value: string,
  key: string,
  payloadSchema: Record<string, PayloadSchemaEntry>
): string | number | boolean {
  const entry = payloadSchema[key];
  const dataType = entry?.data_type?.toLowerCase();
  const lower = value.toLowerCase();

  if (dataType === 'bool' && (lower === 'true' || lower === 'false')) {
    return lower === 'true';
  }

  if ((dataType === 'integer' || dataType === 'int') && value !== '') {
    const parsed = Number(value);
    return Number.isNaN(parsed) ? value : parsed;
  }

  if (dataType === 'float' && value !== '') {
    const parsed = Number(value);
    return Number.isNaN(parsed) ? value : parsed;
  }

  return value;
}

export function parseSimilarInput(rawInput: string): PointId | null {
  const trimmed = (rawInput || '').trim();
  if (!trimmed) {
    return null;
  }

  const idMatch = trimmed.match(/^id\s*:\s*(.+)$/i);
  const valuePart = (idMatch ? idMatch[1] : trimmed).trim();
  if (!valuePart) {
    return null;
  }

  return parseIdValue(valuePart);
}

export function parseFilterString(
  filterText: string,
  payloadSchema: Record<string, PayloadSchemaEntry>
): ParsedFilter[] {
  const tokens = (filterText || '').match(/\S+/g) || [];
  const parsed: ParsedFilter[] = [];

  tokens.forEach((token) => {
    const colonIndex = token.indexOf(':');
    if (colonIndex <= 0) {
      return;
    }

    const key = token.slice(0, colonIndex).trim();
    const rawValue = token.slice(colonIndex + 1).trim();
    if (!key || !rawValue) {
      return;
    }

    if (key.toLowerCase() === 'id') {
      parsed.push({ key: 'id', value: parseIdValue(rawValue), isIdFilter: true });
      return;
    }

    if (rawValue.toLowerCase() === 'null') {
      parsed.push({ key, value: null });
      return;
    }
    if (rawValue === '(empty)') {
      parsed.push({ key, value: '' });
      return;
    }

    parsed.push({ key, value: normalizeBySchema(rawValue, key, payloadSchema) });
  });

  return uniqFilters(parsed);
}

export function buildFilterInputFromFilters(filters: ParsedFilter[]): string {
  return filters
    .map((filter) => {
      if (filter.isIdFilter) {
        return `id:${filter.value}`;
      }

      if (filter.value === null) {
        return `${filter.key}:null`;
      }
      if (filter.value === '') {
        return `${filter.key}:(empty)`;
      }
      return `${filter.key}:${String(filter.value)}`;
    })
    .join(' ');
}

export function buildQdrantFilter(
  filters: ParsedFilter[],
  payloadSchema: Record<string, PayloadSchemaEntry>
): Record<string, unknown> | undefined {
  const idFilters = filters.filter((item) => item.isIdFilter);
  const payloadFilters = filters.filter((item) => !item.isIdFilter);
  const must: Record<string, unknown>[] = [];

  payloadFilters.forEach((filter) => {
    if (filter.value === null) {
      must.push({ is_null: { key: filter.key } });
      return;
    }
    if (filter.value === '') {
      must.push({ is_empty: { key: filter.key } });
      return;
    }

    const schemaEntry = payloadSchema[filter.key];
    if (schemaEntry?.data_type === 'text') {
      must.push({ key: filter.key, match: { text: filter.value } });
      return;
    }
    must.push({ key: filter.key, match: { value: filter.value } });
  });

  if (idFilters.length > 0) {
    must.push({ has_id: idFilters.map((item) => item.value) });
  }

  if (must.length === 0) {
    return undefined;
  }
  return { must };
}

