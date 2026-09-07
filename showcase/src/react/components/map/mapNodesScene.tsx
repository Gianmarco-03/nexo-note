import { useEffect, useMemo, useRef, type MouseEvent, type PointerEvent as ReactPointerEvent } from 'react';
import { DocumentDuplicateIcon, ScissorsIcon, TrashIcon } from '@heroicons/react/24/outline';
import { clamp } from '../../state/store';
import { getNodeAnchorRatios } from './mapConnections';
import type { LinkAnchor, MapNodeEntity } from '../../types/models';

const mapNodeSvgPolygonPoints = {
  trapezoid: [
    { x: 22, y: 8 },
    { x: 78, y: 8 },
    { x: 96, y: 92 },
    { x: 4, y: 92 },
  ],
  diamond: [
    { x: 50, y: 4 },
    { x: 96, y: 50 },
    { x: 50, y: 96 },
    { x: 4, y: 50 },
  ],
  hexagon: [
    { x: 18, y: 8 },
    { x: 82, y: 8 },
    { x: 96, y: 50 },
    { x: 82, y: 92 },
    { x: 18, y: 92 },
    { x: 4, y: 50 },
  ],
};

function parseHexColor(color: string) {
  const value = `${color || ''}`.trim();
  const match = value.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (!match) return null;
  let hex = match[1];
  if (hex.length === 3) hex = hex.split('').map((char) => char + char).join('');
  return {
    r: Number.parseInt(hex.slice(0, 2), 16),
    g: Number.parseInt(hex.slice(2, 4), 16),
    b: Number.parseInt(hex.slice(4, 6), 16),
  };
}

function normalizeHexColor(color: string, fallback = '#5a7cff') {
  const rgb = parseHexColor(color) || parseHexColor(fallback);
  if (!rgb) return '#5a7cff';
  const toHex = (value: number) => value.toString(16).padStart(2, '0');
  return `#${toHex(rgb.r)}${toHex(rgb.g)}${toHex(rgb.b)}`;
}

function toFiniteNumber(value: unknown, fallback: number | null = null) {
  const parsed = Number(value);
  if (Number.isFinite(parsed)) return parsed;
  return fallback;
}

function getDefaultNodeCornerRadius(shape: MapNodeEntity['shape'] = 'rectangle') {
  if (shape === 'circle') return 0;
  if (shape === 'diamond') return 12;
  if (shape === 'trapezoid') return 14;
  if (shape === 'hexagon') return 14;
  return 16;
}

function normalizeNodeCornerRadius(
  value: unknown,
  shape: MapNodeEntity['shape'] = 'rectangle',
  width = 220,
  height = 120,
) {
  if (shape === 'circle') return 0;
  const minSide = Math.max(1, Math.min(Math.abs(toFiniteNumber(width, 220) || 220), Math.abs(toFiniteNumber(height, 120) || 120)));
  const fallback = getDefaultNodeCornerRadius(shape);
  const parsed = toFiniteNumber(value, fallback) || fallback;
  const maxRadius = Math.max(0, Math.round(minSide * 0.24));
  return Math.round(clamp(parsed, 0, maxRadius));
}

function toSvgUnits(value: unknown, width = 220, height = 120) {
  const minSide = Math.max(1, Math.min(Math.abs(toFiniteNumber(width, 220) || 220), Math.abs(toFiniteNumber(height, 120) || 120)));
  const safeValue = Math.max(0, toFiniteNumber(value, 0) || 0);
  return (safeValue / minSide) * 100;
}

function buildRoundedPolygonPath(points: Array<{ x: number; y: number }>, cornerRadius = 0) {
  if (!Array.isArray(points) || points.length < 3) return '';
  const rounded = Math.max(0, toFiniteNumber(cornerRadius, 0) || 0);
  const fmt = (n: number) => Number(n.toFixed(2));

  if (rounded <= 0.01) {
    const [first, ...rest] = points;
    return `M ${fmt(first.x)} ${fmt(first.y)} ${rest.map((p) => `L ${fmt(p.x)} ${fmt(p.y)}`).join(' ')} Z`;
  }

  const corners = points.map((point, index) => {
    const prev = points[(index - 1 + points.length) % points.length];
    const next = points[(index + 1) % points.length];
    const inVec = { x: prev.x - point.x, y: prev.y - point.y };
    const outVec = { x: next.x - point.x, y: next.y - point.y };
    const inLen = Math.hypot(inVec.x, inVec.y);
    const outLen = Math.hypot(outVec.x, outVec.y);
    if (inLen < 0.001 || outLen < 0.001) {
      return { start: { ...point }, end: { ...point }, corner: { ...point } };
    }

    const maxOffset = Math.min(inLen, outLen) * 0.45;
    const offset = Math.min(rounded, maxOffset);
    const inNorm = { x: inVec.x / inLen, y: inVec.y / inLen };
    const outNorm = { x: outVec.x / outLen, y: outVec.y / outLen };
    return {
      start: {
        x: point.x + (inNorm.x * offset),
        y: point.y + (inNorm.y * offset),
      },
      end: {
        x: point.x + (outNorm.x * offset),
        y: point.y + (outNorm.y * offset),
      },
      corner: { ...point },
    };
  });

  let path = `M ${fmt(corners[0].start.x)} ${fmt(corners[0].start.y)}`;
  corners.forEach((entry, index) => {
    path += ` Q ${fmt(entry.corner.x)} ${fmt(entry.corner.y)} ${fmt(entry.end.x)} ${fmt(entry.end.y)}`;
    const nextEntry = corners[(index + 1) % corners.length];
    if (index < corners.length - 1) {
      path += ` L ${fmt(nextEntry.start.x)} ${fmt(nextEntry.start.y)}`;
    }
  });
  path += ' Z';
  return path;
}

function colorWithAlpha(color: string, alpha: number, fallback = '#5a7cff') {
  const rgb = parseHexColor(color) || parseHexColor(fallback) || { r: 93, g: 125, b: 255 };
  const safeAlpha = Math.max(0, Math.min(1, alpha));
  return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${safeAlpha})`;
}

function darkenHexColor(color: string, amount = 0.28, fallback = '#5a7cff') {
  const rgb = parseHexColor(color) || parseHexColor(fallback) || { r: 93, g: 125, b: 255 };
  const ratio = clamp(Number(amount) || 0, 0, 0.92);
  const channel = (value: number) => Math.max(0, Math.min(255, Math.round(value * (1 - ratio))));
  const toHex = (value: number) => value.toString(16).padStart(2, '0');
  return `#${toHex(channel(rgb.r))}${toHex(channel(rgb.g))}${toHex(channel(rgb.b))}`;
}

interface MapNodesSceneProps {
  width: number;
  height: number;
  nodes: MapNodeEntity[];
  selectedNodeIds: string[];
  connectMode: boolean;
  startLinkNodeId: string | null;
  startLinkAnchor: LinkAnchor | null;
  fallbackColor?: string;
  onNodeTextChange: (nodeId: string, text: string, html: string) => void;
  onNodeGeometryChange: (nodeId: string, patch: Partial<MapNodeEntity>) => void;
  editingNodeId: string | null;
  onBeginNodeTextEdit: (nodeId: string) => void;
  onEndNodeTextEdit: () => void;
  onNodeSelect: (nodeId: string, event: MouseEvent<HTMLDivElement>) => void;
  onDeleteNode: (nodeId: string) => void;
  onCopyNode: (nodeId: string) => void;
  onCutNode: (nodeId: string) => void;
  onNodeContextMenu?: (nodeId: string, event: MouseEvent<HTMLDivElement>) => void;
  onPickAnchor: (nodeId: string, anchor: LinkAnchor) => void;
}

interface NodeAnchorDotProps {
  anchor: LinkAnchor;
  x: number;
  y: number;
  active: boolean;
  onPick: () => void;
}

function NodeAnchorDot({ anchor, x, y, active, onPick }: NodeAnchorDotProps) {
  return (
    <button
      type="button"
      className={`node-anchor-dot ${active ? 'active' : ''}`}
      data-anchor={anchor}
      style={{
        left: `${x * 100}%`,
        top: `${y * 100}%`,
      }}
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        onPick();
      }}
      title={`Collega ${anchor}`}
    />
  );
}

function buildPolygonPoints(shape: MapNodeEntity['shape']) {
  if (shape === 'trapezoid') return mapNodeSvgPolygonPoints.trapezoid;
  if (shape === 'diamond') return mapNodeSvgPolygonPoints.diamond;
  if (shape === 'hexagon') return mapNodeSvgPolygonPoints.hexagon;
  return null;
}

function MapNodeShapeSvg({ node, fallbackColor }: { node: MapNodeEntity; fallbackColor: string }) {
  const baseColor = normalizeHexColor(node.color || fallbackColor, fallbackColor);
  const rgb = parseHexColor(baseColor) || parseHexColor(fallbackColor) || { r: 90, g: 124, b: 255 };
  const luminance = ((rgb.r * 299) + (rgb.g * 587) + (rgb.b * 114)) / 1000;
  const borderColor = luminance > 170 ? '#2f3f58' : darkenHexColor(baseColor, 0.52, fallbackColor);
  const fillAlpha = luminance > 205 ? 0.34 : luminance > 175 ? 0.28 : 0.22;
  const fillColor = colorWithAlpha(baseColor, fillAlpha, baseColor);
  const nodeWidth = Math.max(120, Math.round(toFiniteNumber(node.width, 220) || 220));
  const nodeHeight = Math.max(80, Math.round(toFiniteNumber(node.height, 120) || 120));
  const cornerRadius = normalizeNodeCornerRadius(node.cornerRadius, node.shape, nodeWidth, nodeHeight);
  const cornerRadiusSvg = toSvgUnits(cornerRadius, nodeWidth, nodeHeight);
  const polygonPoints = buildPolygonPoints(node.shape);

  if (node.shape === 'circle') {
    return (
      <svg className="map-node-shape" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        <ellipse
          className="map-node-shape-geometry"
          cx="50"
          cy="50"
          rx="43"
          ry="43"
          fill={fillColor}
          stroke={borderColor}
          strokeWidth="3.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    );
  }

  if (polygonPoints) {
    const pathData = buildRoundedPolygonPath(polygonPoints, Math.max(0, Math.min(26, cornerRadiusSvg)));
    return (
      <svg className="map-node-shape" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        <path
          className="map-node-shape-geometry"
          d={pathData}
          fill={fillColor}
          stroke={borderColor}
          strokeWidth="3.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    );
  }

  return (
    <svg className="map-node-shape" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <rect
        className="map-node-shape-geometry"
        x="4"
        y="4"
        width="92"
        height="92"
        rx={Math.max(0, Math.min(32, cornerRadiusSvg))}
        ry={Math.max(0, Math.min(32, cornerRadiusSvg))}
        fill={fillColor}
        stroke={borderColor}
        strokeWidth="3.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

function MapNodeBlock({
  node,
  bounds,
  selected,
  connectMode,
  isStartNode,
  startLinkAnchor,
  fallbackColor,
  onNodeTextChange,
  onNodeGeometryChange,
  isTextEditing,
  onBeginNodeTextEdit,
  onEndNodeTextEdit,
  onNodeSelect,
  onDeleteNode,
  onCopyNode,
  onCutNode,
  onNodeContextMenu,
  onPickAnchor,
}: {
  node: MapNodeEntity;
  bounds: { width: number; height: number };
  selected: boolean;
  connectMode: boolean;
  isStartNode: boolean;
  startLinkAnchor: LinkAnchor | null;
  fallbackColor: string;
  onNodeTextChange: (nodeId: string, text: string, html: string) => void;
  onNodeGeometryChange: (nodeId: string, patch: Partial<MapNodeEntity>) => void;
  isTextEditing: boolean;
  onBeginNodeTextEdit: (nodeId: string) => void;
  onEndNodeTextEdit: () => void;
  onNodeSelect: (nodeId: string, event: MouseEvent<HTMLDivElement>) => void;
  onDeleteNode: (nodeId: string) => void;
  onCopyNode: (nodeId: string) => void;
  onCutNode: (nodeId: string) => void;
  onNodeContextMenu?: (nodeId: string, event: MouseEvent<HTMLDivElement>) => void;
  onPickAnchor: (nodeId: string, anchor: LinkAnchor) => void;
}) {
  const blockRef = useRef<HTMLDivElement | null>(null);
  const textRef = useRef<HTMLDivElement | null>(null);
  const safeNodeX = Math.max(0, Math.round(toFiniteNumber(node.x, 80) || 80));
  const safeNodeY = Math.max(0, Math.round(toFiniteNumber(node.y, 80) || 80));
  const safeNodeWidth = Math.max(120, Math.round(toFiniteNumber(node.width, 220) || 220));
  const safeNodeHeight = Math.max(72, Math.round(toFiniteNumber(node.height, 120) || 120));

  const anchorRatios = useMemo(
    () => getNodeAnchorRatios(node.shape),
    [node.shape],
  );

  useEffect(() => {
    if (!isTextEditing || !textRef.current) return;
    textRef.current.focus();
    const selection = window.getSelection();
    if (!selection) return;
    const range = document.createRange();
    range.selectNodeContents(textRef.current);
    range.collapse(false);
    selection.removeAllRanges();
    selection.addRange(range);
  }, [isTextEditing]);

  const startDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();

    const startX = event.clientX;
    const startY = event.clientY;
    const originX = safeNodeX;
    const originY = safeNodeY;

    const onMove = (moveEvent: PointerEvent) => {
      const dx = moveEvent.clientX - startX;
      const dy = moveEvent.clientY - startY;
      const nextX = clamp(originX + dx, 0, Math.max(0, bounds.width - safeNodeWidth));
      const nextY = clamp(originY + dy, 0, Math.max(0, bounds.height - safeNodeHeight));
      onNodeGeometryChange(node.id, { x: Math.round(nextX), y: Math.round(nextY) });
    };

    const onUp = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };

    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  };

  const startResize = (
    event: ReactPointerEvent<HTMLButtonElement>,
    side: 'top' | 'right' | 'bottom' | 'left' | 'corner',
  ) => {
    event.preventDefault();
    event.stopPropagation();

    const startX = event.clientX;
    const startY = event.clientY;
    const originX = safeNodeX;
    const originY = safeNodeY;
    const originWidth = safeNodeWidth;
    const originHeight = safeNodeHeight;

    const onMove = (moveEvent: PointerEvent) => {
      const dx = moveEvent.clientX - startX;
      const dy = moveEvent.clientY - startY;
      if (side === 'corner') {
        const nextWidth = clamp(originWidth + dx, 120, Math.max(120, bounds.width - safeNodeX));
        const nextHeight = clamp(originHeight + dy, 72, Math.max(72, bounds.height - safeNodeY));
        onNodeGeometryChange(node.id, {
          width: Math.round(nextWidth),
          height: Math.round(nextHeight),
        });
        return;
      }
      if (side === 'right') {
        const nextWidth = clamp(originWidth + dx, 120, Math.max(120, bounds.width - safeNodeX));
        onNodeGeometryChange(node.id, { width: Math.round(nextWidth) });
        return;
      }
      if (side === 'bottom') {
        const nextHeight = clamp(originHeight + dy, 72, Math.max(72, bounds.height - safeNodeY));
        onNodeGeometryChange(node.id, { height: Math.round(nextHeight) });
        return;
      }
      if (side === 'left') {
        const nextX = clamp(originX + dx, 0, originX + originWidth - 120);
        const nextWidth = clamp(originWidth - (nextX - originX), 120, bounds.width - nextX);
        onNodeGeometryChange(node.id, {
          x: Math.round(nextX),
          width: Math.round(nextWidth),
        });
        return;
      }
      const nextY = clamp(originY + dy, 0, originY + originHeight - 72);
      const nextHeight = clamp(originHeight - (nextY - originY), 72, bounds.height - nextY);
      onNodeGeometryChange(node.id, {
        y: Math.round(nextY),
        height: Math.round(nextHeight),
      });
    };

    const onUp = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };

    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  };

  return (
    <div
      ref={blockRef}
      className={`block map-node shape-${node.shape || 'rectangle'} ${selected ? 'selected' : ''} ${connectMode ? 'connect-mode' : ''}`}
      data-map-node-id={node.id}
      data-element-id={node.id}
      style={{
        left: `${safeNodeX}px`,
        top: `${safeNodeY}px`,
        width: `${safeNodeWidth}px`,
        height: `${safeNodeHeight}px`,
        background: 'transparent',
      }}
      onClick={(event) => {
        event.stopPropagation();
        onNodeSelect(node.id, event);
      }}
      onContextMenu={(event) => {
        if (!onNodeContextMenu) return;
        event.preventDefault();
        event.stopPropagation();
        onNodeContextMenu(node.id, event);
      }}
    >
      <MapNodeShapeSvg node={node} fallbackColor={fallbackColor} />

      <div className="block-drag-handle map-drag-handle" onPointerDown={startDrag} />

      <div className="block-action-tools map-node-action-tools" onClick={(event) => event.stopPropagation()}>
        <button type="button" className="block-action-btn" onClick={() => onDeleteNode(node.id)} title="Elimina">
          <TrashIcon />
        </button>
        <button type="button" className="block-action-btn" onClick={() => onCutNode(node.id)} title="Taglia">
          <ScissorsIcon />
        </button>
        <button type="button" className="block-action-btn" onClick={() => onCopyNode(node.id)} title="Copia">
          <DocumentDuplicateIcon />
        </button>
      </div>

      <div className="block-content">
        <div
          ref={textRef}
          className={`node-text ${isTextEditing ? 'editing' : 'locked'}`}
          contentEditable={isTextEditing}
          suppressContentEditableWarning
          onInput={(event) => {
            const target = event.currentTarget;
            onNodeTextChange(node.id, target.textContent || '', target.innerHTML || '');
          }}
          dangerouslySetInnerHTML={{ __html: node.html || node.text || '' }}
          onDoubleClick={(event) => {
            event.stopPropagation();
            onBeginNodeTextEdit(node.id);
          }}
          onBlur={(event) => {
            onNodeTextChange(node.id, event.currentTarget.textContent || '', event.currentTarget.innerHTML || '');
            if (isTextEditing) onEndNodeTextEdit();
          }}
          onClick={(event) => {
            if (connectMode || isTextEditing) return;
            event.stopPropagation();
          }}
        />
      </div>

      {!connectMode && (
        <>
          <button className="node-resize-handle side-top" type="button" onPointerDown={(event) => startResize(event, 'top')} />
          <button className="node-resize-handle side-right" type="button" onPointerDown={(event) => startResize(event, 'right')} />
          <button className="node-resize-handle side-bottom" type="button" onPointerDown={(event) => startResize(event, 'bottom')} />
          <button className="node-resize-handle side-left" type="button" onPointerDown={(event) => startResize(event, 'left')} />
          <button className="node-resize-handle corner-bottom-right" type="button" onPointerDown={(event) => startResize(event, 'corner')} />
        </>
      )}

      {connectMode && (
        <div className="node-anchor-layer visible" onClick={(event) => event.stopPropagation()}>
          {(Object.keys(anchorRatios) as LinkAnchor[]).map((anchorKey) => {
            const point = anchorRatios[anchorKey];
            return (
              <NodeAnchorDot
                key={anchorKey}
                anchor={anchorKey}
                x={point.x}
                y={point.y}
                active={Boolean(isStartNode && startLinkAnchor === anchorKey)}
                onPick={() => onPickAnchor(node.id, anchorKey)}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

export function MapNodesScene({
  width,
  height,
  nodes,
  selectedNodeIds,
  connectMode,
  startLinkNodeId,
  startLinkAnchor,
  fallbackColor = '#5a7cff',
  onNodeTextChange,
  onNodeGeometryChange,
  editingNodeId,
  onBeginNodeTextEdit,
  onEndNodeTextEdit,
  onNodeSelect,
  onDeleteNode,
  onCopyNode,
  onCutNode,
  onNodeContextMenu,
  onPickAnchor,
}: MapNodesSceneProps) {
  return (
    <div className="map-nodes-scene" style={{ width: `${width}px`, height: `${height}px` }}>
      {nodes.map((node) => (
        <MapNodeBlock
          key={node.id}
          node={node}
          bounds={{ width, height }}
          selected={selectedNodeIds.includes(node.id)}
          connectMode={connectMode}
          isStartNode={startLinkNodeId === node.id}
          startLinkAnchor={startLinkAnchor}
          fallbackColor={fallbackColor}
          onNodeTextChange={onNodeTextChange}
          onNodeGeometryChange={onNodeGeometryChange}
          isTextEditing={editingNodeId === node.id}
          onBeginNodeTextEdit={onBeginNodeTextEdit}
          onEndNodeTextEdit={onEndNodeTextEdit}
          onNodeSelect={onNodeSelect}
          onDeleteNode={onDeleteNode}
          onCopyNode={onCopyNode}
          onCutNode={onCutNode}
          onNodeContextMenu={onNodeContextMenu}
          onPickAnchor={onPickAnchor}
        />
      ))}
    </div>
  );
}
