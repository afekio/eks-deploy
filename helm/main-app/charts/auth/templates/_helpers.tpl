{{/*
Resolve the full container image reference.
Uses per-service image.* overrides, falling back to global.image.*.
*/}}
{{- define "auth.image" -}}
{{- $registry := .Values.image.registry | default .Values.global.image.registry -}}
{{- $repository := .Values.image.repository | default .Values.global.image.repository -}}
{{- printf "%s/%s:%s" $registry $repository .Values.image.tag -}}
{{- end -}}

{{- define "auth.pullPolicy" -}}
{{- .Values.image.pullPolicy | default .Values.global.image.pullPolicy -}}
{{- end -}}

{{- define "auth.name" -}}
{{- .Values.nameOverride | default "auth" -}}
{{- end -}}

{{- define "auth.labels" -}}
app: {{ include "auth.name" . }}
app.kubernetes.io/name: {{ include "auth.name" . }}
app.kubernetes.io/part-of: main-app
app.kubernetes.io/component: auth
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "auth.selectorLabels" -}}
app: {{ include "auth.name" . }}
{{- end -}}
