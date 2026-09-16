{{- define "star-warehouse-ai.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "star-warehouse-ai.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "star-warehouse-ai.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "star-warehouse-ai.labels" -}}
helm.sh/chart: {{ include "star-warehouse-ai.chart" . }}
app.kubernetes.io/name: {{ include "star-warehouse-ai.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "star-warehouse-ai.selectorLabels" -}}
app.kubernetes.io/name: {{ include "star-warehouse-ai.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "star-warehouse-ai.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "star-warehouse-ai.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- required "serviceAccount.name is required when serviceAccount.create=false" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{- define "star-warehouse-ai.image" -}}
{{- if .Values.image.digest -}}
{{- printf "%s@%s" .Values.image.repository .Values.image.digest -}}
{{- else if .Values.productionMode -}}
{{- fail "image.digest is required when productionMode=true" -}}
{{- else -}}
{{- $tag := required "image.tag is required when image.digest is empty" .Values.image.tag -}}
{{- if and (eq $tag "latest") (not .Values.image.allowMutableTag) -}}
{{- fail "image tag latest is forbidden unless allowMutableTag=true in a non-production profile" -}}
{{- end -}}
{{- printf "%s:%s" .Values.image.repository $tag -}}
{{- end -}}
{{- end -}}

{{- define "star-warehouse-ai.podAnnotations" -}}
checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
star-warehouse-ai.io/secret-ref: {{ required "secretRef.name is required" .Values.secretRef.name | quote }}
{{- if .Values.image.buildRevision }}
org.opencontainers.image.revision: {{ .Values.image.buildRevision | quote }}
{{- end }}
{{- end -}}

{{- define "star-warehouse-ai.imagePullSecrets" -}}
{{- with .Values.image.pullSecrets }}
imagePullSecrets:
{{- range . }}
  - name: {{ . | quote }}
{{- end }}
{{- end }}
{{- end -}}

{{- define "star-warehouse-ai.runtimeEnvFrom" -}}
envFrom:
  - configMapRef:
      name: {{ include "star-warehouse-ai.fullname" . }}
{{- end -}}

{{- define "star-warehouse-ai.runtimeEnv" -}}
- name: PYTHONDONTWRITEBYTECODE
  value: "1"
- name: APP_BUILD_REVISION
  value: {{ default "unknown" .Values.image.buildRevision | quote }}
- name: REDIS_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .Values.secretRef.name }}
      key: REDIS_PASSWORD
- name: QDRANT_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.secretRef.name }}
      key: QDRANT_API_KEY
- name: CELERY_BROKER_URL
  valueFrom:
    secretKeyRef:
      name: {{ .Values.secretRef.name }}
      key: CELERY_BROKER_URL
- name: CELERY_RESULT_BACKEND
  valueFrom:
    secretKeyRef:
      name: {{ .Values.secretRef.name }}
      key: CELERY_RESULT_BACKEND
- name: SECRET_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.secretRef.name }}
      key: SECRET_KEY
- name: OPENAI_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.secretRef.name }}
      key: OPENAI_API_KEY
- name: DASHSCOPE_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.secretRef.name }}
      key: DASHSCOPE_API_KEY
- name: OIDC_CLIENT_SECRET
  valueFrom:
    secretKeyRef:
      name: {{ .Values.secretRef.name }}
      key: OIDC_CLIENT_SECRET
      optional: true
- name: BUSINESS_API_TOKEN
  valueFrom:
    secretKeyRef:
      name: {{ .Values.secretRef.name }}
      key: BUSINESS_API_TOKEN
      optional: true
- name: SMTP_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .Values.secretRef.name }}
      key: SMTP_PASSWORD
      optional: true
- name: LANGSMITH_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.secretRef.name }}
      key: LANGSMITH_API_KEY
      optional: true
{{- end -}}

{{- define "star-warehouse-ai.databaseEnv" -}}
{{- $root := .root -}}
{{- if eq .capability "maintenance" }}
- name: POSTGRES_USER
  value: {{ $root.Values.config.POSTGRES_MAINTENANCE_USER | quote }}
- name: POSTGRES_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ $root.Values.secretRef.name }}
      key: POSTGRES_MAINTENANCE_PASSWORD
- name: POSTGRES_MAINTENANCE_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ $root.Values.secretRef.name }}
      key: POSTGRES_MAINTENANCE_PASSWORD
{{- else }}
- name: POSTGRES_USER
  value: {{ $root.Values.config.POSTGRES_RUNTIME_USER | quote }}
- name: POSTGRES_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ $root.Values.secretRef.name }}
      key: POSTGRES_RUNTIME_PASSWORD
- name: POSTGRES_RUNTIME_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ $root.Values.secretRef.name }}
      key: POSTGRES_RUNTIME_PASSWORD
{{- end }}
{{- end -}}

{{- define "star-warehouse-ai.migrationInitContainer" -}}
{{- $root := .root -}}
- name: migration-ready
  image: {{ include "star-warehouse-ai.image" $root | quote }}
  imagePullPolicy: {{ $root.Values.image.pullPolicy }}
  command: ["alembic", "current", "--check-heads"]
  {{- include "star-warehouse-ai.runtimeEnvFrom" $root | nindent 2 }}
  env:
    {{- include "star-warehouse-ai.runtimeEnv" $root | nindent 4 }}
    {{- include "star-warehouse-ai.databaseEnv" (dict "root" $root "capability" .capability) | nindent 4 }}
    - name: DB_CAPABILITY
      value: {{ .capability }}
  resources:
    requests:
      cpu: 25m
      memory: 128Mi
    limits:
      cpu: 250m
      memory: 256Mi
  securityContext:
    {{- toYaml $root.Values.containerSecurityContext | nindent 4 }}
{{- end -}}

{{- define "star-warehouse-ai.volumeMounts" -}}
- name: tmp
  mountPath: /tmp
- name: cache
  mountPath: /app/.cache
- name: uploads
  mountPath: /app/uploads
{{- end -}}

{{- define "star-warehouse-ai.volumes" -}}
- name: tmp
  emptyDir: {}
- name: cache
  emptyDir: {}
- name: uploads
  emptyDir: {}
{{- end -}}

{{- define "star-warehouse-ai.demoSecretName" -}}
{{- default .Values.secretRef.name .Values.demoInfrastructure.secretRefName -}}
{{- end -}}
