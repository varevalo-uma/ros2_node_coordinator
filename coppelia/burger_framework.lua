sim = require('sim')
simROS2 = require('simROS2')
json = require('dkjson')

-- ============================
-- Configuration
-- ============================
WHEEL_BASE = 0.16
WHEEL_RADIUS = 0.033

initial_position = nil
initial_quaternion = nil

status = 'stopped' -- 'stopped' | 'playing'

-- Generate Gaussian-distributed noise used when resetting odometry pose.
local function randn(mean, sigma)
    local u1 = math.random()
    local u2 = math.random()
    if u1 < 1e-12 then u1 = 1e-12 end
    local z0 = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
    return mean + sigma * z0
end

-- Multiply quaternions q1 * q2 to compose frame rotations.
local function quatMultiply(q1, q2)
    return {
        q1[4] * q2[1] + q1[1] * q2[4] + q1[2] * q2[3] - q1[3] * q2[2],
        q1[4] * q2[2] - q1[1] * q2[3] + q1[2] * q2[4] + q1[3] * q2[1],
        q1[4] * q2[3] + q1[1] * q2[2] - q1[2] * q2[1] + q1[3] * q2[4],
        q1[4] * q2[4] - q1[1] * q2[1] - q1[2] * q2[2] - q1[3] * q2[3]
    }
end

-- Build a std_msgs/String-compatible ACK payload encoded as JSON.
local function make_ack_message(node_name, ack_status)
    local encoded = json.encode({
        node = node_name,
        status = ack_status,
    })

    return {
        data = encoded,
    }
end

-- Publish an acknowledgment in the expected coordinator format.
local function publish_ack(publisher, node_name, ack_status)
    simROS2.publish(publisher, make_ack_message(node_name, ack_status))
end

-- Extract the "config" map from a coordinator command message.
local function load_config(message)
    local payload = json.decode(message.data)
    if type(payload) ~= 'table' then
        return {}
    end
    return payload.config or {}
end

-- Parse a positive floating-point value or return a fallback.
local function safe_float(value, fallback)
    local numeric = tonumber(value)
    if numeric == nil or numeric <= 0.0 then
        return fallback
    end
    return numeric
end

-- Initialize scene handles, ROS interfaces, and control subscriptions.
function sysCall_init()
    -- Robot
    robotHandle = sim.getObject('/Burger')
    robotAlias = sim.getObjectAlias(robotHandle)

    -- Base link and wheels
    baseLinkHandle = sim.getObject('/base_link_' .. robotAlias)
    baseLinkAlias = sim.getObjectAlias(baseLinkHandle)
    motorLeft = sim.getObject('/wheel_left_joint')
    motorRight = sim.getObject('/wheel_right_joint')

    -- Laser
    laserHandle = sim.getObject('/laser_' .. robotAlias)
    laserAlias = sim.getObjectAlias(laserHandle)

    -- IR ring
    irLeftHandle = sim.getObject('/ring_' .. robotAlias .. '/left_' .. robotAlias)
    irLeftAlias = sim.getObjectAlias(irLeftHandle)
    irRightHandle = sim.getObject('/ring_' .. robotAlias .. '/right_' .. robotAlias)
    irRightAlias = sim.getObjectAlias(irRightHandle)

    -- Odom reference dummy
    odomHandle = sim.createDummy(0.01)
    odomAlias = 'odom_' .. robotAlias
    sim.setObjectAlias(odomHandle, odomAlias)

    initial_position = sim.getObjectPosition(robotHandle, -1)
    initial_quaternion = sim.getObjectQuaternion(robotHandle, -1)
    sim.setObjectPosition(odomHandle, -1, initial_position)
    sim.setObjectQuaternion(odomHandle, -1, initial_quaternion)

    poseGt = sim.addDrawingObject(sim.drawing_linestrip, 3, 0, -1, 1000, {1, 0, 0})

    if not simROS2 then
        error('[Coppelia] simROS2 not available.')
    end

    -- Clock bridge publication
    pub_clock = simROS2.createPublisher('/clock_coppelia', 'builtin_interfaces/msg/Time')

    -- Odometry publication
    pub_odometry = simROS2.createPublisher(robotAlias .. '/odom', 'nav_msgs/msg/Odometry')

    -- Optional robot velocity command input
    simROS2.createSubscription('/teleop/cmd_vel_delayed', 'geometry_msgs/msg/Twist', 'cmd_vel_callback')

    -- Coordinator-driven control topics
    simROS2.createSubscription(robotAlias .. '/play', 'std_msgs/msg/String', 'play_callback')
    pub_play_ack = simROS2.createPublisher(robotAlias .. '/play_ack', 'std_msgs/msg/String')

    simROS2.createSubscription(robotAlias .. '/stop', 'std_msgs/msg/String', 'stop_callback')
    pub_stop_ack = simROS2.createPublisher(robotAlias .. '/stop_ack', 'std_msgs/msg/String')

    print('[Coppelia] Initialized, waiting for play/stop commands.')
end

--------------------------------------------------------
-- Velocity callback
--------------------------------------------------------
-- Handle incoming velocity commands and drive wheel targets.
function cmd_vel_callback(msg)
    -- Ignore velocity commands until coordinator transitions the robot to playing.
    if status ~= 'playing' then
        return
    end

    local v = msg.linear.x or 0.0
    local w = msg.angular.z or 0.0
    local vLeft, vRight

    if math.abs(w) > 1e-9 then
        local radius = v / w
        vLeft = w * (radius - WHEEL_BASE / 2)
        vRight = w * (radius + WHEEL_BASE / 2)
    else
        vLeft = v
        vRight = v
    end

    sim.setJointTargetVelocity(motorLeft, vLeft / WHEEL_RADIUS)
    sim.setJointTargetVelocity(motorRight, vRight / WHEEL_RADIUS)

    local pose = sim.getObjectPosition(baseLinkHandle, -1)
    sim.addDrawingObjectItem(poseGt, pose)
end

--------------------------------------------------------
-- Play / stop callbacks
--------------------------------------------------------
-- Handle a coordinator play command and publish play ACK.
function play_callback(msg)
    -- Keep ACK idempotent when duplicate play commands arrive.
    if status == 'playing' then
        print('[Coppelia] Already playing, ignoring new /play')
        publish_ack(pub_play_ack, robotAlias, 'playing')
        return
    end

    local config = load_config(msg)
    status = 'playing'

    print('[Coppelia] Playing with config:\n' .. msg.data)

    local play_delay = safe_float(config[robotAlias .. '_play_sec'], 0.10)
    if config.play_sec ~= nil then
        play_delay = safe_float(config.play_sec, play_delay)
    end
    sim.wait(play_delay, false)

    publish_ack(pub_play_ack, robotAlias, 'playing')
end

-- Handle a coordinator stop command and publish stop ACK.
function stop_callback(msg)
    -- Keep ACK idempotent when duplicate stop commands arrive.
    if status == 'stopped' then
        print('[Coppelia] Already stopped, ignoring new /stop')
        publish_ack(pub_stop_ack, robotAlias, 'stopped')
        return
    end

    local config = load_config(msg)
    status = 'stopped'

    reset_pose(config)

    local stop_delay = safe_float(config[robotAlias .. '_stop_sec'], 0.10)
    if config.stop_sec ~= nil then
        stop_delay = safe_float(config.stop_sec, stop_delay)
    end
    sim.wait(stop_delay, false)

    print('[Coppelia] Stopped by /stop')
    publish_ack(pub_stop_ack, robotAlias, 'stopped')
end

-- Stop the robot and reset pose/odom references with optional noise.
function reset_pose(config)
    sim.setJointTargetVelocity(motorLeft, 0)
    sim.setJointTargetVelocity(motorRight, 0)

    local y_noise = safe_float(config.odom_y_noise, 0.05)
    local new_position = {
        initial_position[1],
        initial_position[2] + randn(0.0, y_noise),
        initial_position[3]
    }

    sim.setObjectPosition(odomHandle, -1, new_position)
    sim.setObjectQuaternion(odomHandle, -1, initial_quaternion)

    sim.setObjectPosition(robotHandle, odomHandle, {0, 0, 0})
    sim.setObjectQuaternion(robotHandle, odomHandle, {0, 0, 0, 1})

    sim.resetDynamicObject(robotHandle)
    sim.resetDynamicObject(motorLeft)
    sim.resetDynamicObject(motorRight)

    sim.addDrawingObjectItem(poseGt, nil)
end

--------------------------------------------------------
-- TF utilities
--------------------------------------------------------
-- Build a transform message from two Coppelia object handles.
function get_transform_stamped(now, childHandle, childName, parentHandle, parentName, applyFix)
    -- Build a TransformStamped-like table consumed by simROS2.sendTransform.
    local p = sim.getObjectPosition(childHandle, parentHandle)
    local q = sim.getObjectQuaternion(childHandle, parentHandle)

    if applyFix then
        local q_fix = {0, -0.7071, 0, 0.7071}
        q = quatMultiply(q, q_fix)
    end

    return {
        header = {
            stamp = now,
            frame_id = parentName
        },
        child_frame_id = childName,
        transform = {
            translation = { x = p[1], y = p[2], z = p[3] },
            rotation = { x = q[1], y = q[2], z = q[3], w = q[4] }
        }
    }
end

--------------------------------------------------------
-- Actuation
--------------------------------------------------------
-- Publish clock, TF tree, and odometry every simulation step.
function sysCall_actuation()
    -- Publish simulation clock every actuation step.
    local now = simROS2.getSimulationTime()
    local time_msg = {
        sec = now.sec,
        nanosec = now.nanosec
    }
    simROS2.publish(pub_clock, time_msg)

    -- Publish TF tree for map->odom->base and sensor frames.
    simROS2.sendTransform(get_transform_stamped(now, odomHandle, odomAlias, -1, 'map', false))
    simROS2.sendTransform(get_transform_stamped(now, baseLinkHandle, baseLinkAlias, odomHandle, odomAlias, false))
    simROS2.sendTransform(get_transform_stamped(now, laserHandle, laserAlias, baseLinkHandle, baseLinkAlias, false))
    simROS2.sendTransform(get_transform_stamped(now, irLeftHandle, irLeftAlias, baseLinkHandle, baseLinkAlias, true))
    simROS2.sendTransform(get_transform_stamped(now, irRightHandle, irRightAlias, baseLinkHandle, baseLinkAlias, true))

    -- Publish odometry in the odom frame.
    local p = sim.getObjectPosition(baseLinkHandle, odomHandle)
    local q = sim.getObjectQuaternion(baseLinkHandle, odomHandle)
    local odom_msg = {
        header = {
            stamp = now,
            frame_id = odomAlias
        },
        child_frame_id = baseLinkAlias,
        pose = {
            pose = {
                position = {x = p[1], y = p[2], z = p[3]},
                orientation = {x = q[1], y = q[2], z = q[3], w = q[4]}
            },
            covariance = {}
        }
    }

    simROS2.publish(pub_odometry, odom_msg)
end

-- Reserved sensing callback for future sensor processing.
function sysCall_sensing()
end

-- Reserved cleanup callback for ROS/resource deallocation if needed.
function sysCall_cleanup()
end
