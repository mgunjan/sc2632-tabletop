# One small stand-in image for every fictional Trustfall Financial workload. It does nothing but stay up,
# serve HTTP on 8080 and TCP on whatever PORT says, so NetworkPolicy, drain/PDB and evidence
# capture can be exercised on real Pods. Built locally from busybox; nothing is pulled at run time.
ARG BASE=busybox:1.36
FROM ${BASE}
RUN mkdir -p /www && echo "trustfall lab stand-in" > /www/index.html
COPY entrypoint.sh /entrypoint.sh
USER 65534:65534
ENTRYPOINT ["/bin/sh", "/entrypoint.sh"]
