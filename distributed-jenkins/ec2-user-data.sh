#!/bin/bash
sudo sysctl -w fs.inotify.max_user_watches=524288
sudo sysctl -w fs.inotify.max_user_instances=10000
sudo sysctl -w  kernel.pid_max=4194304

echo "install docker production"
sudo yum install -y yum-utils device-mapper-persistent-data lvm2
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo yum update -y && sudo yum install -y containerd.io-1.4.3 docker-ce-20.10.2 docker-ce-cli-20.10.2
sudo mkdir /etc/docker

cat <<EOF | sudo tee /etc/docker/daemon.json
{
  "exec-opts": ["native.cgroupdriver=systemd"],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m"
  },
  "storage-driver": "overlay2",
  "storage-opts": [
    "overlay2.override_kernel_check=true"
  ]
}
EOF

sudo mkdir -p /etc/systemd/system/docker.service.d
sudo systemctl daemon-reload
sudo systemctl restart docker
sudo systemctl enable docker
sudo chmod 666 /var/run/docker.sock
echo "docker installation done"

sudo yum install unzip -y
curl "https://s3.amazonaws.com/aws-cli/awscli-bundle.zip" -o "awscli-bundle.zip"
unzip awscli-bundle.zip
sudo ./awscli-bundle/install -i /usr/local/aws -b /usr/local/bin/aws
sudo aws --version
sudo rm awscli-bundle.zip
echo "aws installation done"

aws configure set aws_access_key_id AKIAUEMMQ4CWH5234Q6Z
aws configure set aws_secret_access_key 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
aws configure set default.region us-west-2

instance_id=$(curl http://169.254.169.254/latest/meta-data/instance-id)
echo $instance_id
vol_id=$(aws ec2 describe-volumes --region us-west-2 --filters Name=attachment.instance-id,Values=$instance_id --query 'Volumes[*].[VolumeId, State==`attached`]'  --output text  | awk '{print $1}')
echo $vol_id
aws ec2 modify-volume --volume-id $vol_id --size 300
sudo growpart /dev/nvme0n1 2
sudo xfs_growfs -d /
echo `lsblk`

sudo echo 'tmpfs /tmp tmpfs size=50G 0 0' > /etc/fstab
sudo mount -a
sudo mkdir -p /tmp/etcd
sudo chmod -R 777 /tmp/etcd


