#!/usr/bin/env groovy
def nodes = [:]

nodesByLabel('cls-1-10').each {
  nodes[it] = { ->
    node(it) {
      stage("preparation@${it}") {

        sh('sudo yum install git -y')
        sh('sudo growpart /dev/nvme0n1 2 && sudo xfs_growfs -d /')
        sh('lsblk')
        sh('sudo mkdir -p /tmp/etcd && sudo chmod -R 777 /tmp/etcd')

        dir('/home/centos/workspace/exhaust-master') {
            checkout scm
        }

        sh('curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.8.1/kind-linux-amd64')
        sh('chmod +x kind')
        sh('echo "" > kind.config')
        sh('''cat <<EOF | sudo tee kind.config
---
apiVersion: kind.x-k8s.io/v1alpha4
kind: Cluster
nodes: 
  - role: control-plane
  - role: worker
  - role: worker
  - role: worker
  - role: worker
kubeadmConfigPatches:
- |
  kind: ClusterConfiguration
  metadata:
    name: config
  etcd:
    local:
      dataDir: "/tmp/etcd"
        ''')
        sh('sudo chmod -R 777 /home/centos/workspace/exhaust-master')
        
        def uuid1 = Math.abs(new Random().nextInt() % 100000) + 1
        sh('''/home/centos/workspace/exhaust-master/kind create cluster --name cls1-5-'''+ uuid1 +''' --config /home/centos/workspace/exhaust-master/kind.config''')

        def uuid2 = Math.abs(new Random().nextInt() % 100000) + 1
        sh('''/home/centos/workspace/exhaust-master/kind create cluster --name cls1-5-'''+ uuid2 + ''' --config /home/centos/workspace/exhaust-master/kind.config''')
        
        sh('docker build -t 477502 -f Dockerfile .')
        sh('docker run --name execution -t -d -u 997:994 --volume-driver=nfs --network=host --privileged -v /home/centos/workspace/exhaust-master:/home/centos/workspace/exhaust-master -v /var/run/docker.sock:/var/run/docker.sock 477502:latest')
        sh('''docker exec -i execution /bin/bash -c "cd /home/centos/workspace/exhaust-master && export ONBOARD=true && export WORKSPACE=/home/centos/workspace/exhaust-master && python3.7 library/pyfra.py --tests-dir setup/client_cluster --cluster-type kind --clusters cls1-5-''' + uuid1+''',cls1-5-'''+uuid2+''' --log-dir . --debug --csp-token kJfh2ZsImeLwv3AT7zGuTFTuRv8OpdIkydseLluytz3pdU6rajZBP3aHV1HQoOCW --clusters-per-tenant 1 --apps-per-cluster 17"''')

        // staging-0 3cd92ae5-2a1e-4c65-88e8-c653aa1e6f55
        //sh('''docker exec -i execution /bin/bash -c "cd /home/centos/workspace/exhaust-master && export ONBOARD=true && export WORKSPACE=/home/centos/workspace/exhaust-master && python3.7 library/pyfra.py --tests-dir setup/client_cluster --cluster-type kind --clusters cls1-5-''' + uuid1+''' --log-dir . --debug --csp-token P8ewTR1jva1zc8y7g3JyvXJyoit7Xodfzj7QFNnLs66YOKDCDIWSznFu4dbrrWyv --clusters-per-tenant 1 --apps-per-cluster 17"''')        
        //sh('''docker exec -i execution /bin/bash -c "cd /home/centos/workspace/exhaust-master && export ONBOARD=true && export WORKSPACE=/home/centos/workspace/exhaust-master && python3.7 library/pyfra.py --tests-dir setup/client_cluster --cluster-type kind --clusters cls1-5-''' + uuid1+''' --log-dir . --debug --csp-token P8ewTR1jva1zc8y7g3JyvXJyoit7Xodfzj7QFNnLs66YOKDCDIWSznFu4dbrrWyv --clusters-per-tenant 1 --apps-per-cluster 18"''')        
        //sh('df -mh')
        //sh('free -mh')

        }
    }
  }
}

parallel nodes
