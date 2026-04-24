ARG ES_VERSION=8.12.2
FROM docker.elastic.co/elasticsearch/elasticsearch:${ES_VERSION}

ARG ES_VERSION

RUN elasticsearch-plugin install --batch "https://get.infini.cloud/elasticsearch/analysis-ik/${ES_VERSION}"
