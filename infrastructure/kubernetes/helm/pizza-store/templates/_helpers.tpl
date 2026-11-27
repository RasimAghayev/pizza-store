{{/*
Chart name and version label, Helm v4 Chart API v2 convention.
*/}}
{{- define "pizza-store.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Common labels applied to every object.
*/}}
{{- define "pizza-store.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ include "pizza-store.chart" . }}
{{- end -}}

{{/*
Per-component selector labels -- usage: include "pizza-store.selectorLabels" (dict "root" . "component" "backend")
*/}}
{{- define "pizza-store.selectorLabels" -}}
app.kubernetes.io/name: {{ .root.Chart.Name }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app: {{ .component }}
{{- end -}}
