// Type declarations for Uppy packages
// These provide basic types when the module resolution doesn't find Uppy's built-in types

declare module '@uppy/core' {
    export interface UppyFile<M = Record<string, unknown>, B = Record<string, unknown>> {
        id: string;
        name: string;
        type?: string;
        data: Blob | File;
        size?: number;
        meta: M & { name?: string; type?: string };
        progress?: {
            percentage?: number;
            bytesUploaded?: number;
            bytesTotal?: number;
            uploadStarted?: number;
            uploadComplete?: boolean;
        };
        response?: {
            body?: B;
            status?: number;
            uploadURL?: string;
        };
        isPaused?: boolean;
        isRemote?: boolean;
    }

    export interface UploadResult<M = Record<string, unknown>, B = Record<string, unknown>> {
        successful: UppyFile<M, B>[];
        failed: UppyFile<M, B>[];
    }

    export interface UppyOptions<M = Record<string, unknown>, B = Record<string, unknown>> {
        id?: string;
        autoProceed?: boolean;
        allowMultipleUploadBatches?: boolean;
        restrictions?: {
            maxNumberOfFiles?: number | null;
            minNumberOfFiles?: number | null;
            maxFileSize?: number | null;
            minFileSize?: number | null;
            maxTotalFileSize?: number | null;
            allowedFileTypes?: string[] | null;
        };
        meta?: M;
        onBeforeFileAdded?: (currentFile: UppyFile<M, B>, files: Record<string, UppyFile<M, B>>) => UppyFile<M, B> | boolean | undefined;
        onBeforeUpload?: (files: Record<string, UppyFile<M, B>>) => Record<string, UppyFile<M, B>> | boolean;
    }

    export default class Uppy<M = Record<string, unknown>, B = Record<string, unknown>> {
        constructor(opts?: UppyOptions<M, B>);

        use<T>(plugin: T, opts?: Record<string, unknown>): this;

        addFile(file: {
            name: string;
            type?: string;
            data: Blob | File;
            meta?: Record<string, unknown>;
        }): string;

        removeFile(fileId: string): void;
        getFiles(): UppyFile<M, B>[];
        getFile(fileId: string): UppyFile<M, B> | undefined;

        upload(): Promise<UploadResult<M, B> | undefined>;
        cancelAll(): void;
        destroy(): void;

        getPlugin<T>(name: string): T | undefined;

        on(event: 'file-added', callback: (file: UppyFile<M, B>) => void): this;
        on(event: 'file-removed', callback: (file: UppyFile<M, B>) => void): this;
        on(event: 'upload-progress', callback: (file: UppyFile<M, B> | undefined, progress: { bytesUploaded: number; bytesTotal: number }) => void): this;
        on(event: 'upload-success', callback: (file: UppyFile<M, B> | undefined, response: Record<string, unknown>) => void): this;
        on(event: 'upload-error', callback: (file: UppyFile<M, B> | undefined, error: Error) => void): this;
        on(event: 'complete', callback: (result: UploadResult<M, B>) => void): this;
        on(event: 'error', callback: (error: Error) => void): this;
        on(event: string, callback: (...args: unknown[]) => void): this;

        off(event: string, callback: (...args: unknown[]) => void): this;
    }
}

declare module '@uppy/tus' {
    import type Uppy from '@uppy/core';

    export interface TusOptions {
        endpoint?: string;
        headers?: Record<string, string> | (() => Record<string, string>);
        chunkSize?: number;
        retryDelays?: number[];
        removeFingerprintOnSuccess?: boolean;
        uploadDataDuringCreation?: boolean;
        onBeforeRequest?: (req: { setHeader: (name: string, value: string) => void }) => Promise<void> | void;
        onAfterResponse?: (req: unknown, res: unknown) => Promise<void> | void;
    }

    export default class Tus {
        constructor(uppy: Uppy, opts?: TusOptions);
        setOptions(opts: Partial<TusOptions>): void;
    }
}
