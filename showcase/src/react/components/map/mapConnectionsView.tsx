import { useState, type MouseEvent } from 'react';
import { DocumentDuplicateIcon, ScissorsIcon, TrashIcon } from '@heroicons/react/24/outline';
import { resolveMapLinks } from './mapConnections';
import type { MapLinkEntity, MapNodeEntity } from '../../types/models';

interface MapConnectionsViewProps {
  width: number;
  height: number;
  markerPrefix: string;
  nodes: MapNodeEntity[];
  links: MapLinkEntity[];
  selectedLinkId: string | null;
  onSelectLink?: (linkId: string) => void;
  onDeleteLink?: (linkId: string) => void;
  onCopyLink?: (linkId: string) => void;
  onCutLink?: (linkId: string) => void;
}

export function MapConnectionsView({
  width,
  height,
  markerPrefix,
  nodes,
  links,
  selectedLinkId,
  onSelectLink,
  onDeleteLink,
  onCopyLink,
  onCutLink,
}: MapConnectionsViewProps) {
  const [hoveredLinkId, setHoveredLinkId] = useState<string | null>(null);
  const resolvedLinks = resolveMapLinks(nodes, links, selectedLinkId);
  const markerEndId = `${markerPrefix}-end`;
  const markerStartId = `${markerPrefix}-start`;

  return (
    <svg className="connections-layer" viewBox={`0 0 ${width} ${height}`} width={width} height={height}>
      <defs>
        <marker id={markerEndId} markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L10,4 L0,8 z" fill="context-stroke" />
        </marker>
        <marker id={markerStartId} markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto-start-reverse" markerUnits="strokeWidth">
          <path d="M0,0 L10,4 L0,8 z" fill="context-stroke" />
        </marker>
      </defs>

      {resolvedLinks.map((link) => {
        const showActions = link.selected || hoveredLinkId === link.id;
        return (
          <g key={link.id}>
            <path
              d={link.path}
              fill="none"
              stroke={link.color}
              strokeWidth={link.strokeWidth}
              className={`map-link-path ${link.selected ? 'selected' : ''}`}
              markerStart={link.markerStart ? `url(#${markerStartId})` : undefined}
              markerEnd={link.markerEnd ? `url(#${markerEndId})` : undefined}
              strokeDasharray={link.dashPattern || undefined}
              onMouseEnter={() => setHoveredLinkId(link.id)}
              onMouseLeave={() => setHoveredLinkId((prev) => (prev === link.id ? null : prev))}
              onClick={(event: MouseEvent<SVGPathElement>) => {
                if (!onSelectLink) return;
                event.preventDefault();
                event.stopPropagation();
                onSelectLink(link.id);
              }}
            />

            {showActions && (
              <g
                className="map-link-action-tools visible"
                transform={`translate(${Math.round(link.midpoint.x - 37)} ${Math.round(link.midpoint.y - 11)})`}
                onMouseEnter={() => setHoveredLinkId(link.id)}
                onMouseLeave={() => setHoveredLinkId((prev) => (prev === link.id ? null : prev))}
              >
                <g
                  className="map-link-action-btn"
                  transform="translate(0 0)"
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    if (onDeleteLink) onDeleteLink(link.id);
                  }}
                >
                  <rect x="0" y="0" width="22" height="22" rx="7" ry="7" />
                  <TrashIcon x="3" y="3" width="16" height="16" aria-hidden="true" />
                </g>

                <g
                  className="map-link-action-btn"
                  transform="translate(26 0)"
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    if (onCutLink) onCutLink(link.id);
                  }}
                >
                  <rect x="0" y="0" width="22" height="22" rx="7" ry="7" />
                  <ScissorsIcon x="3" y="3" width="16" height="16" aria-hidden="true" />
                </g>

                <g
                  className="map-link-action-btn"
                  transform="translate(52 0)"
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    if (onCopyLink) onCopyLink(link.id);
                  }}
                >
                  <rect x="0" y="0" width="22" height="22" rx="7" ry="7" />
                  <DocumentDuplicateIcon x="3" y="3" width="16" height="16" aria-hidden="true" />
                </g>
              </g>
            )}
          </g>
        );
      })}
    </svg>
  );
}
