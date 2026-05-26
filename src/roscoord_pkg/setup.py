from setuptools import find_packages, setup

package_name = 'roscoord_pkg'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', [
            'launch/framework.launch.py'
        ]),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='varevalo',
    maintainer_email='varevalo@uma.es',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'clock_bridge = roscoord_pkg.clock_bridge:main',
            'coordinator = roscoord_pkg.coordinator:main',
            'nodo1 = roscoord_pkg.nodo1:main',
            'nodo2 = roscoord_pkg.nodo2:main',
        ],
    },
)
