import React, { useCallback, useRef } from 'react';
import { FileValidation, ValidationRules } from '../types';

interface FileUploadZoneProps {
    files: File[];
    validations: FileValidation[];
    rules: ValidationRules;
    onFilesAdded: (files: File[]) => void;
    onFileRemoved: (index: number) => void;
    disabled?: boolean;
}

const FileUploadZone: React.FC<FileUploadZoneProps> = ({
    files,
    validations,
    rules,
    onFilesAdded,
    onFileRemoved,
    disabled,
}) => {
    const inputRef = useRef<HTMLInputElement>(null);
    const [isDragging, setIsDragging] = React.useState(false);

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        if (!disabled) {
            setIsDragging(true);
        }
    }, [disabled]);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
    }, []);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);

        if (disabled) return;

        const droppedFiles = Array.from(e.dataTransfer.files);
        if (droppedFiles.length > 0) {
            onFilesAdded(droppedFiles);
        }
    }, [disabled, onFilesAdded]);

    const handleClick = useCallback(() => {
        if (!disabled && inputRef.current) {
            inputRef.current.click();
        }
    }, [disabled]);

    const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFiles = Array.from(e.target.files || []);
        if (selectedFiles.length > 0) {
            onFilesAdded(selectedFiles);
        }
        // Reset input so the same file can be selected again
        if (inputRef.current) {
            inputRef.current.value = '';
        }
    }, [onFilesAdded]);

    const formatFileSize = (bytes: number): string => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    const remainingFiles = rules.fileCount - files.length;

    return (
        <div className="space-y-4">
            {/* Drop Zone */}
            <div
                onClick={handleClick}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`relative border-2 border-dashed rounded-lg p-8 flex flex-col items-center justify-center text-center transition-all cursor-pointer ${
                    isDragging
                        ? 'border-primary bg-red-50/50'
                        : 'border-border-light hover:border-primary/50 hover:bg-surface-light'
                } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
                style={{
                    backgroundImage: 'radial-gradient(circle, #e5e7eb 1px, transparent 1px)',
                    backgroundSize: '24px 24px',
                }}
            >
                <input
                    ref={inputRef}
                    type="file"
                    accept=".xlsx"
                    multiple
                    onChange={handleInputChange}
                    className="hidden"
                    disabled={disabled}
                />
                <div className={`h-12 w-12 rounded-full bg-surface-light border border-border-light flex items-center justify-center mb-4 ${
                    isDragging ? 'bg-white text-primary' : 'text-text-sub'
                }`}>
                    <span className="material-symbols-outlined text-[24px]">upload_file</span>
                </div>
                <p className="text-sm font-medium text-text-main">
                    Drag & drop or click to upload
                </p>
                <p className="text-xs text-text-sub mt-1">
                    {remainingFiles > 0
                        ? `Select ${remainingFiles} more .xlsx file${remainingFiles > 1 ? 's' : ''} (min ${rules.minSizeKb}KB each)`
                        : 'All required files selected'}
                </p>
            </div>

            {/* File List */}
            {files.length > 0 && (
                <div className="space-y-2">
                    <div className="flex items-center justify-between">
                        <span className="text-[10px] font-bold text-text-sub uppercase tracking-wider">
                            Selected Files ({files.length}/{rules.fileCount})
                        </span>
                    </div>
                    <div className="border border-border-light rounded divide-y divide-border-light bg-white">
                        {files.map((file, index) => {
                            const validation = validations[index];
                            const isValid = validation?.isValid !== false;

                            return (
                                <div
                                    key={`${file.name}-${index}`}
                                    className="flex items-center justify-between px-4 py-3 hover:bg-surface-light transition-colors"
                                >
                                    <div className="flex items-center gap-3 min-w-0">
                                        <div className={`w-8 h-8 rounded flex items-center justify-center ${
                                            isValid ? 'bg-green-50 border border-green-100' : 'bg-red-50 border border-red-100'
                                        }`}>
                                            <span className={`material-symbols-outlined text-[16px] ${
                                                isValid ? 'text-green-600' : 'text-red-600'
                                            }`}>
                                                {isValid ? 'description' : 'error'}
                                            </span>
                                        </div>
                                        <div className="min-w-0">
                                            <p className="text-sm font-medium text-text-main truncate" title={file.name}>
                                                {file.name}
                                            </p>
                                            <div className="flex items-center gap-2 text-xs text-text-sub">
                                                <span className="font-mono">{formatFileSize(file.size)}</span>
                                                {!isValid && validation?.error && (
                                                    <>
                                                        <span className="w-1 h-1 rounded-full bg-border-dark"></span>
                                                        <span className="text-red-600">{validation.error}</span>
                                                    </>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => onFileRemoved(index)}
                                        disabled={disabled}
                                        className="p-1 text-text-sub hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                                    >
                                        <span className="material-symbols-outlined text-[18px]">close</span>
                                    </button>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
};

export default FileUploadZone;
