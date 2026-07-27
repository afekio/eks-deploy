{{- define "backend.image" -}}
{{- $registry := .Values.image.registry | default .Values.global.image.registry -}}
{{- $repository := .Values.image.repository | default .Values.global.image.repository -}}
{{- printf "%s/%s:%s" $registry $repository .Values.image.tag -}}
{{- end -}}

{{- define "backend.pullPolicy" -}}
{{- .Values.image.pullPolicy | default .Values.global.image.pullPolicy -}}
{{- end -}}

{{- define "backend.name" -}}
{{- .Values.nameOverride | default "backend" -}}
{{- end -}}

{{- define "backend.labels" -}}
app: {{ include "backend.name" . }}
app.kubernetes.io/name: {{ include "backend.name" . }}
app.kubernetes.io/part-of: main-app
app.kubernetes.io/component: backend
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "backend.selectorLabels" -}}
app: {{ include "backend.name" . }}
{{- end -}}
