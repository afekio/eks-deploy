{{- define "frontend.image" -}}
{{- $registry := .Values.image.registry | default .Values.global.image.registry -}}
{{- $repository := .Values.image.repository | default .Values.global.image.repository -}}
{{- printf "%s/%s:%s" $registry $repository .Values.image.tag -}}
{{- end -}}

{{- define "frontend.pullPolicy" -}}
{{- .Values.image.pullPolicy | default .Values.global.image.pullPolicy -}}
{{- end -}}

{{- define "frontend.name" -}}
{{- .Values.nameOverride | default "frontend" -}}
{{- end -}}

{{- define "frontend.labels" -}}
app: {{ include "frontend.name" . }}
app.kubernetes.io/name: {{ include "frontend.name" . }}
app.kubernetes.io/part-of: main-app
app.kubernetes.io/component: frontend
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "frontend.selectorLabels" -}}
app: {{ include "frontend.name" . }}
{{- end -}}
