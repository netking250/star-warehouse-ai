import { useRef, useState } from 'react'
import { FileText, Loader2, Play, Trash2, Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useKnowledgeBase, useSyncStatus } from '@/hooks/useKnowledgeBase'
import {
  adminTableClassName,
  DataPanel,
  DataTableShell,
  PageHeader,
  SectionHeader,
  StatusBadge,
  type StatusTone,
} from './AdminPrimitives'
import { ConsoleEmptyState, ConsolePageSkeleton } from './ConsoleState'

function formatBytes(bytes: number | null): string {
  if (bytes == null) return '—'
  if (bytes === 0) return '0 Bytes'
  const index = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${parseFloat((bytes / 1024 ** index).toFixed(2))} ${['Bytes', 'KB', 'MB', 'GB'][index]}`
}

function statusPresentation(status: string): { tone: StatusTone; label: string; loading: boolean } {
  if (status === 'done') return { tone: 'success', label: 'Synced', loading: false }
  if (status === 'running' || status === 'STARTED' || status === 'PENDING') {
    return { tone: 'info', label: 'Processing', loading: true }
  }
  if (status === 'failed') return { tone: 'danger', label: 'Failed', loading: false }
  return { tone: 'neutral', label: status || 'Unknown', loading: false }
}

function SyncBadge({ status }: { status: string }): React.ReactElement {
  const view = statusPresentation(status)
  return (
    <StatusBadge tone={view.tone} pulse={view.loading}>
      {view.label}
    </StatusBadge>
  )
}

export function KnowledgeBaseManager(): React.ReactElement {
  const {
    documents,
    isLoading,
    uploadDocument,
    isUploading,
    deleteDocument,
    isDeleting,
    syncDocument,
    isSyncing,
  } = useKnowledgeBase()
  const [lastTaskId, setLastTaskId] = useState<string | null>(null)
  const { data: syncStatus } = useSyncStatus(lastTaskId)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>): Promise<void> => {
    const file = event.target.files?.[0]
    if (!file) return
    try {
      const result = await uploadDocument(file)
      if (result.task_id) setLastTaskId(result.task_id)
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  if (isLoading) return <ConsolePageSkeleton />
  const activeSync = syncStatus?.status === 'PENDING' || syncStatus?.status === 'STARTED'

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Knowledge"
        title="Knowledge inventory"
        description="Ingest, inspect, and synchronize tenant knowledge sources through the existing storage and indexing workflow."
        status={
          <StatusBadge tone={activeSync ? 'info' : 'success'} pulse={activeSync}>
            {activeSync ? 'Indexing in progress' : `${documents.length} sources available`}
          </StatusBadge>
        }
        actions={
          <Button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
          >
            {isUploading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Upload className="h-4 w-4" />
            )}
            {isUploading ? 'Uploading…' : 'Add source'}
          </Button>
        }
      />

      <input
        type="file"
        ref={fileInputRef}
        className="sr-only"
        onChange={(event) => void handleUpload(event)}
        accept=".txt,.md,.json,.pdf"
        aria-label="Upload knowledge document"
      />

      <DataPanel className="overflow-hidden">
        <div className="border-b border-border-subtle p-5">
          <SectionHeader
            title="Ingestion workspace"
            description="Accepted formats: TXT, Markdown, JSON, and PDF. Uploaded sources keep their real processing state."
            icon={Upload}
          />
        </div>
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
          className="group m-5 flex min-h-28 w-[calc(100%-2.5rem)] items-center justify-center gap-4 rounded-lg border border-dashed border-primary/25 bg-primary/[0.035] px-5 text-left transition-[background-color,border-color] hover:border-primary/45 hover:bg-primary/[0.065] disabled:cursor-not-allowed disabled:opacity-60"
        >
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-md border border-primary/15 bg-surface-elevated text-primary shadow-sm">
            <Upload className="h-5 w-5" aria-hidden="true" />
          </span>
          <span>
            <span className="block text-sm font-semibold text-foreground">
              Choose a knowledge source
            </span>
            <span className="mt-1 block text-xs text-muted-foreground">
              Processing begins through the existing tenant-bound upload API.
            </span>
          </span>
        </button>
        {activeSync && syncStatus && (
          <div
            className="mx-5 mb-5 flex items-center gap-3 rounded-md border border-info/20 bg-info/10 px-4 py-3 text-sm text-info"
            role="status"
          >
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            Sync task <span className="font-mono text-xs">{syncStatus.task_id}</span> is processing.
          </div>
        )}
      </DataPanel>

      <DataPanel className="p-5">
        <SectionHeader
          title="Document inventory"
          description="Current source metadata, indexing state, and supported actions."
          icon={FileText}
          action={<StatusBadge>{documents.length} documents</StatusBadge>}
        />
        <div className="mt-5">
          {documents.length === 0 ? (
            <ConsoleEmptyState
              title="No knowledge sources yet"
              description="Add a supported document to begin the existing ingestion workflow."
            />
          ) : (
            <DataTableShell>
              <table className={`${adminTableClassName} min-w-[720px]`}>
                <thead>
                  <tr>
                    <th>Source</th>
                    <th>Type</th>
                    <th>Size</th>
                    <th>Status</th>
                    <th>Processing detail</th>
                    <th className="text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((document) => (
                    <tr key={document.id}>
                      <td>
                        <div className="flex items-center gap-3">
                          <span className="grid h-8 w-8 place-items-center rounded-md bg-muted text-muted-foreground">
                            <FileText className="h-4 w-4" aria-hidden="true" />
                          </span>
                          <span className="font-medium text-foreground">{document.filename}</span>
                        </div>
                      </td>
                      <td className="text-muted-foreground">{document.content_type}</td>
                      <td className="numeric text-muted-foreground">
                        {formatBytes(document.doc_size_bytes)}
                      </td>
                      <td>
                        <SyncBadge status={document.sync_status} />
                      </td>
                      <td className="max-w-xs text-xs text-muted-foreground">
                        {document.sync_message || '—'}
                      </td>
                      <td>
                        <div className="flex justify-end gap-1">
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            onClick={() =>
                              void syncDocument(document.id).then(
                                (result) => result.task_id && setLastTaskId(result.task_id)
                              )
                            }
                            disabled={isSyncing}
                            aria-label={`Sync ${document.filename}`}
                            title="Sync to vector index"
                          >
                            <Play className="h-4 w-4" aria-hidden="true" />
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            onClick={() => void deleteDocument(document.id)}
                            disabled={isDeleting}
                            aria-label={`Delete ${document.filename}`}
                            className="text-danger hover:bg-danger/10 hover:text-danger"
                          >
                            <Trash2 className="h-4 w-4" aria-hidden="true" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </DataTableShell>
          )}
        </div>
      </DataPanel>
    </div>
  )
}
