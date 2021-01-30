FROM centos:7
RUN yum -y --enablerepo=extras install epel-release && yum clean all && yum -y update
RUN yum -y install wget
RUN yum -y install make
RUN yum install gcc -y
RUN yum install zlib-devel -y
RUN yum install libffi-devel -y
RUN yum install openssl-devel -y
RUN wget https://www.python.org/ftp/python/3.7.2/Python-3.7.2.tgz && tar xzf Python-3.7.2.tgz
RUN cd Python-3.7.2 && ./configure --enable-optimizations && make altinstall
RUN rm Python-3.7.2.tgz

USER root
RUN yum install dnf -y
RUN yum install sudo -y
RUN sudo yum -y install epel-release
RUN sudo yum -y install jq -y
RUN yum install --assumeyes python3-pip
RUN pip3 --version
RUN pip3 install --target=/usr/local/lib/python3.7/site-packages requests
RUN pip3 install --target=/usr/local/lib/python3.7/site-packages kubernetes
RUN pip3 install --target=/usr/local/lib/python3.7/site-packages pandas
RUN pip3 install --target=/usr/local/lib/python3.7/site-packages matplotlib 
RUN pip3 install --target=/usr/local/lib/python3.7/site-packages prettytable

RUN yum install unzip -y
RUN curl "https://s3.amazonaws.com/aws-cli/awscli-bundle.zip" -o "awscli-bundle.zip"
RUN unzip awscli-bundle.zip
RUN sudo ./awscli-bundle/install -i /usr/local/aws -b /usr/local/bin/aws
RUN aws --version
RUN rm awscli-bundle.zip

ADD tsm_apis /
ADD prometheus /
ADD library /
ADD setup /
ADD istio /

RUN echo $'[kubernetes] \n\
name=Kubernetes \n\
baseurl=https://packages.cloud.google.com/yum/repos/kubernetes-el7-x86_64 \n\
enabled=1 \n\
gpgcheck=1 \n\
repo_gpgcheck=1 \n\
gpgkey=https://packages.cloud.google.com/yum/doc/yum-key.gpg https://packages.cloud.google.com/yum/doc/rpm-package-key.gpg \n '\
> /etc/yum.repos.d/kubernetes.repo
RUN yum install -y kubectl

ARG USER_ID=997
ARG GROUP_ID=994
RUN groupadd -g $GROUP_ID centos && \
    useradd -u $USER_ID -s /bin/sh -g centos centos
RUN echo "root:root" | chpasswd
RUN echo "centos:centos" | chpasswd
RUN echo "centos ALL=(ALL) ALL" > /etc/sudoers
RUN echo "centos ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers

ARG DOCKER_CLIENT=docker-20.10.2.tgz

RUN cd /tmp/ && curl -sSL -O https://download.docker.com/linux/static/stable/x86_64/docker-20.10.2.tgz\
&& tar zxf docker-20.10.2.tgz \
&& mkdir -p /usr/local/bin \
&& mv ./docker/docker /usr/local/bin \
&& chmod +x /usr/local/bin/docker \
&& rm -rf /tmp/*