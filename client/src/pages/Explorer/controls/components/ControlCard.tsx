import React from 'react';
import { ControlWithDetails } from '../types';
import { ControlCardBasic } from './ControlCardBasic';
import { ControlCardRelationships } from './ControlCardRelationships';
import { ControlCardAI } from './ControlCardAI';

interface Props {
    item: ControlWithDetails;
}

export const ControlCard: React.FC<Props> = ({ item }) => {
    return (
        <div className="bg-white border border-border-light rounded shadow-subtle hover:shadow-card transition-shadow flex flex-col md:flex-row">
            {/* Section 1: Basic Details */}
            <div className="flex-[2] min-w-0 md:border-r md:border-border-light">
                <ControlCardBasic control={item.control} relationships={item.relationships} />
            </div>

            {/* Section 2: Relationships */}
            <div className="flex-[1.5] min-w-0 border-t md:border-t-0 md:border-r md:border-border-light border-border-light">
                <ControlCardRelationships
                    relationships={item.relationships}
                />
            </div>

            {/* Section 3: AI Enrichment */}
            <div className="flex-[1.5] min-w-0 border-t md:border-t-0 border-border-light bg-surface-light/50 rounded-b md:rounded-bl-none md:rounded-r">
                <ControlCardAI ai={item.ai} parentScore={item.parentL1Score} similarControls={item.similarControls} />
            </div>
        </div>
    );
};
