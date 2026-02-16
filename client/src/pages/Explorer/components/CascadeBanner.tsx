import React from 'react';
import { CascadeSuggestion } from '../hooks/useCascadeSuggestions';

interface CascadeBannerProps {
    suggestion: CascadeSuggestion;
    onAccept: () => void;
    onDismiss: () => void;
}

export const CascadeBanner: React.FC<CascadeBannerProps> = ({
    suggestion,
    onAccept,
    onDismiss,
}) => {
    return (
        <div className="flex items-start gap-1.5 px-2 py-1.5 bg-blue-50 border border-blue-200 rounded-sm mb-1.5">
            <span className="material-symbols-outlined text-[14px] text-blue-600 mt-0.5 flex-shrink-0">
                link
            </span>
            <div className="flex-1 min-w-0">
                <p className="text-[10px] text-blue-800 leading-tight">
                    {suggestion.message}
                </p>
                <div className="flex items-center gap-2 mt-1">
                    <button
                        onClick={onAccept}
                        className="text-[10px] font-medium text-blue-700 hover:text-blue-900 underline"
                    >
                        Select
                    </button>
                    <button
                        onClick={onDismiss}
                        className="text-[10px] font-medium text-blue-500 hover:text-blue-700"
                    >
                        Dismiss
                    </button>
                </div>
            </div>
        </div>
    );
};
