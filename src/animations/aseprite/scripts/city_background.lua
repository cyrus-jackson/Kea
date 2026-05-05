local canvasWidth = 200
local canvasHeight = 300

sprite = Sprite(canvasWidth, canvasHeight)
app.activeSprite = sprite

local brush1 = Brush {
    type = BrushType.CIRCLE,
    size = 1
}
local brush2 = Brush {
    type = BrushType.CIRCLE,
    size = 2
}

------------------------------------------------------------------------------------------------------------------------
function genWindows(buildingStartX, buildingEndX, buildingStartY, buildingEndY, windowWidth, windowHeight, windowColour1, windowColour2)

    -- Working out window size and number
    local buildingWidth = buildingEndX - buildingStartX
    local buildingHeight = buildingEndY - buildingStartY

    -- Number of windows is building width minus 2 for buffer either side, divided by four (window width + buffer)
    local windowsInRow = (buildingWidth - 2) / windowWidth
    local windowsInColumn = (buildingHeight - 2) / windowHeight

    -- Window loops
    local iy
    local ix
    for iy = 0, windowsInColumn, 1 do

        for ix = 0, windowsInRow, 1 do

            local windowStartX = buildingStartX + 1 + (ix * windowWidth)
            local windowStartY = buildingStartY + 3 + (iy * windowHeight)
            local windowEndX = windowStartX + windowWidth - 2
            local windowEndY = windowStartY + windowHeight - 3

            if windowEndX < buildingEndX then

                local drawWindowChance = math.random(1, 10)

                if drawWindowChance >= 7 then

                    local colourTable = {windowColour1, windowColour1, windowColour1, windowColour2}
                    local chosenColour = colourTable[math.random(#colourTable)]

                    app.useTool {
                        tool = "filled_rectangle",
                        color = chosenColour,
                        brush = brush1,
                        points = {
                            Point(windowStartX, windowStartY),
                            Point(windowEndX, windowEndY)
                        },
                        cel = cel,
                        layer = layer
                    }

                end
            end
        end

    ix = 0
        
    end
end

function genBuildings(buildingWidth, buildingHeight, buildingStartX, buildingColour, windowWidth, windowHeight, windowColour1, windowColour2)

    -- Building creation loop
    local i
    for i = 0, buildingWidth, 1 do

        buildingStartX = buildingWidth * i + math.random( -buildingWidth, buildingWidth)
        local buildingStartY = buildingHeight + math.random( -15, 15)
        local buildingEndX = buildingStartX + buildingWidth + math.random(-10, 10)
        local buildingEndY = canvasHeight
        
        app.useTool {
            tool = "filled_rectangle",
            color = buildingColour,
            brush = brush1,
            points = {
                Point(buildingStartX, buildingStartY),
                Point(buildingEndX, buildingEndY)
            },
            cel = cel,
            layer = layer
        }

        -- Choose a feature to add
        local featureTable = {
            "Box",
            "Dome",
            "Light",
            "Platform",
            "Pylon",
            "None"
        }
        local chosenFeature = featureTable[math.random(#featureTable)]

        if chosenFeature == "Box" then

            local boxStartX = math.random(buildingStartX, buildingStartX + (buildingWidth/2))
            local boxStartY = math.random(buildingStartY - 5, buildingStartY - 1)
            local boxEndX = math.random(buildingStartX + (buildingWidth/2), buildingEndX)
            local boxEndY = buildingStartY

            app.useTool {
                tool = "filled_rectangle",
                color = buildingColour,
                brush = brush1,
                points = {
                    Point(boxStartX, boxStartY),
                    Point(boxEndX, boxEndY)
                },
                cel = cel,
                layer = layer
            }

        elseif chosenFeature == "Dome" then

            local domeDiameterMin = (buildingEndX - buildingStartX)/2
            local domeDiameterMax = buildingEndX - buildingStartX

            local domeDiameter = math.random(domeDiameterMin, domeDiameterMax)
            local domeRadius = domeDiameter/2

            -- Start point is the midway point of the building, minus the dome radius
            local domeStartX = (buildingStartX + ((buildingEndX - buildingStartX)/2)) - domeRadius
            local domeStartY = math.random(buildingStartY - domeRadius, buildingStartY - (domeRadius/2))
            local domeEndX = (buildingStartX + ((buildingEndX - buildingStartX)/2)) + domeRadius
            local domeEndY = math.random(buildingStartY + (domeRadius/2), buildingStartY + domeRadius)

            app.useTool {
                tool = "filled_ellipse",
                color = buildingColour,
                brush = brush1,
                points = {
                    Point(domeStartX, domeStartY),
                    Point(domeEndX, domeEndY)
                },
                cel = cel,
                layer = layer
            }

        elseif chosenFeature == "Light" then

            local lightColour = Color{ h=5, s=0.6, v=1, a=255 }

            app.useTool {
                tool = "pencil",
                color = lightColour,
                brush = brush1,
                points = {Point(buildingStartX + 2, buildingStartY - 1) },
                cel = cel,
                layer = layer
            }
            app.useTool {
                tool = "pencil",
                color = lightColour,
                brush = brush1,
                points = {
                Point(buildingEndX - 1, buildingStartY - 1) },
                cel = cel,
                layer = layer
            }
        elseif chosenFeature == "Platform" then

            app.useTool {
                tool = "line",
                color = buildingColour,
                brush = brush1,
                points = {
                    Point(buildingStartX, buildingStartY - 2),
                    Point(buildingEndX, buildingStartY - 2)
                },
                cel = cel,
                layer = layer
            }
            app.useTool {
                tool = "pencil",
                color = buildingColour,
                brush = brush1,
                points = { Point(buildingStartX + 3, buildingStartY - 1) },
                cel = cel,
                layer = layer
            }
            app.useTool {
                tool = "pencil",
                color = buildingColour,
                brush = brush1,
                points = { Point(buildingEndX - 2, buildingStartY - 1) },
                cel = cel,
                layer = layer
            }
        elseif chosenFeature == "Pylon" then

            local pylonPosition = math.random(buildingStartX, buildingEndX)
            local pylonHeight = math.random(2, 6)

            app.useTool {
                tool = "line",
                color = buildingColour,
                brush = brush1,
                points = {
                    Point(pylonPosition, buildingStartY),
                    Point(pylonPosition, buildingStartY - pylonHeight)
                },
                cel = cel,
                layer = layer
            }

        end

        -- Windows
        windowWidthCurrent = math.random(windowWidth - 1, windowWidth + 1)
        windowHeightCurrent = math.random(windowHeight - 1, windowHeight + 1)

        genWindows(buildingStartX, buildingEndX, buildingStartY, buildingEndY, windowWidthCurrent, windowHeightCurrent, windowColour1, windowColour2)

    end

end

function genRoad(roadPositionY, roadThickness, roadColour)

    app.useTool {
        tool = "filled_rectangle",
        color = roadColour,
        brush = brush1,
        points = {
            Point(0, roadPositionY),
            Point(canvasWidth, roadPositionY + roadThickness)
        },
        cel = cel,
        layer = layer
    }

    local numberOfStruts = canvasWidth/roadThickness
    local strutWidth = (roadThickness / 3) * 2
    local strutInterval = strutWidth * 5

    -- For loop to draw struts at fixed intervals left to right, half roadThickness
    local i
    for i = 0, numberOfStruts, 1 do

        local strutPosition = i * strutInterval + (i * strutWidth)

        -- Draw struts
        app.useTool {
            tool = "filled_rectangle",
            color = roadColour,
            brush = brush1,
            points = {
                Point(strutPosition, roadPositionY),
                Point(strutPosition + strutWidth, canvasHeight)
            },
            cel = cel,
            layer = layer
        }

        -- Draw arches
        app.useTool {
            tool = "line",
            color = roadColour,
            brush = brush1,
            points = {
                Point(strutPosition - 2, roadPositionY + roadThickness + 1),
                Point(strutPosition + strutWidth + 2, roadPositionY + roadThickness + 1)
            },
            cel = cel,
            layer = layer
    }

    end

    local railingChance = math.random(0, 1)
    if railingChance > 0 then

        -- Draw railing/barrier
        app.useTool {
            tool = "line",
            color = roadColour,
            brush = brush1,
            points = {
                Point(0, roadPositionY - roadThickness/2),
                Point(canvasWidth, roadPositionY - roadThickness/2)
            },
            cel = cel,
            layer = layer
        }

        local numberOfPoles = canvasWidth/2
        local poleWidth = 1
        local poleInterval = 2
                
        local poleStart = math.random(-10, 10)

        -- Loop to draw railing poles
        local i
        for i = 0, numberOfPoles, 1 do

            local polePosition = poleStart + i * poleInterval + (i * poleWidth)

            -- Draw struts
            app.useTool {
                tool = "filled_rectangle",
                color = roadColour,
                brush = brush1,
                points = {
                    Point(polePosition, roadPositionY - roadThickness/2),
                    Point(polePosition + poleWidth, roadPositionY)
                },
                cel = cel,
                layer = layer
            }
        end
    end

    -- Draw streetlamps
    local numberOfLamps = canvasWidth/4
    local lampWidth = 1
    local lampHeight = 8
    local lampInterval = 24

    local lampStart = math.random(-10, 10)

    -- Loop to draw lamps
    local i
    for i = 0, numberOfLamps, 1 do

        local lampPosition = lampStart + i * lampInterval + (i * lampWidth)

        -- Draw post
        app.useTool {
            tool = "filled_rectangle",
            color = roadColour,
            brush = brush1,
            points = {
                Point(lampPosition, roadPositionY - lampHeight),
                Point(lampPosition + lampWidth - 1, roadPositionY)
            },
            cel = cel,
            layer = layer
        }

        -- Draw head
        app.useTool {
            tool = "filled_rectangle",
            color = roadColour,
            brush = brush1,
            points = {
                Point(lampPosition, roadPositionY - lampHeight),
                Point(lampPosition + lampWidth + 1, roadPositionY - lampHeight + 1)
            },
            cel = cel,
            layer = layer
        }

        -- Draw light
        app.useTool {
            tool = "pencil",
            color = Color{ h=45, s=0.1, v=1, a=255 },
            brush = brush2,
            points = { Point(lampPosition + 3, roadPositionY - lampHeight + 2) },
            cel = cel,
            layer = layer
        }

    end

end

function genTraffic(numberOfCars, moveSpeed)

    local tableCarPositions = {}
    local trafficOffset = canvasWidth * moveSpeed

    for i = 0, numberOfCars, 2 do
    tableCarPositions[i] = math.random(0, canvasWidth)
    tableCarPositions[i + 1] = tableCarPositions[i] - trafficOffset
    end

    return tableCarPositions

end

function drawTraffic(trafficTable, trafficBrush, trafficSpeed, trafficPositionY, trafficLayer, trafficCel, frameNumber)

    -- Iterate through traffic table
    local ti = 0
    for ti, value in ipairs(trafficTable) do

        app.useTool {
            tool = "pencil",
            color = Color(255, 255, 255, 255),
            brush = trafficBrush,
            points = { Point(trafficTable[ti] + (trafficSpeed * frameNumber), trafficPositionY - 1) }, 
            cel = trafficCel,
            layer = trafficLayer,
        }
    end
end

function moveReflectionSegment(i, sectionIncrement)
    
    local moveDir = table.remove(tableDirections)
    table.insert(tableDirections, 1, moveDir)

    sprite.selection = Selection(Rectangle, i, canvasWidth, sectionIncrement)

    if moveDir == "hold" then
    else
        app.command.MoveMask {
            target = 'content',
            direction = moveDir,
            units = "pixel",
            quantity = 1,
            wrap = false
        }
    end
    app.command.DeselectMask()

end

function animateReflection(startPoint)

    local breakPoint1 = canvasHeight * 0.80
    local breakPoint2 = canvasHeight * 0.90
    local breakPoint3 = canvasHeight * 0.95
    local breakPoint4 = canvasHeight

    -- Reflection section 1
    for i = startPoint, breakPoint1, 1 do
        moveReflectionSegment(i, 1)
    end
        
    -- Reflection section 2
    for i = breakPoint1 + 1, breakPoint2, 2 do
        moveReflectionSegment(i, 2)
    end

    -- Reflection section 3
    for i = breakPoint2 + 2, breakPoint3, 3 do
        moveReflectionSegment(i, 3)
    end

    -- Reflection section 4
    for i = breakPoint3 + 3, breakPoint4, 4 do
        moveReflectionSegment(i, 4)
    end
    
end

------------------------------------------------------------------------------------------------------------------------
-- Colour generation
local baseHue = math.random(360)
local baseSat = math.random(15, 40) /100
local baseVal = math.random(81, 100) /100

local baseColour = Color{ h=baseHue, s=baseSat, v=baseVal, a=255 }

------------------------------------------------------------------------------------------------------------------------
-- Create new layer and new cel
local skyLayer = sprite:newLayer()
skyLayer.name = "sky"
local cel = sprite:newCel(skyLayer, 1)

-- Paint bucket at point
app.useTool {
    tool = "paint_bucket",
    color = baseColour,
    brush = brush1,
    points = { Point(1, 1) },
    cel = cel,
    layer = skyLayer
}

------------------------------------------------------------------------------------------------------------------------
-- Create new layer
local starLayer = sprite:newLayer()
starLayer.name = "stars"
local cel = sprite:newCel(starLayer, 1)

-- Choose how many stars to draw
local numberStars = math.random(20, 40)

local tableBrushes = {brush, brush2}
	
-- Draw stars at random positions this number of times
local i
for i = 0, numberStars, 1 do

    -- Choose the x and y coords
    local starXCoord = math.random(0, canvasWidth)
    local starYCoord = math.random(0, canvasHeight)

    local chosenBrush = tableBrushes[math.random(#tableBrushes)]

    -- Pencil tool at point
    app.useTool {
        tool = "pencil",
        color = Color{ h=0, s=0, v=1, a=255 },
        brush = chosenBrush,
        points = { Point(starXCoord, starYCoord) },
        cel = cel,
        layer = starLayer
    }
    
end

-- Choose the x and y coords
local sphereXCoord = math.random(6, canvasWidth - 6)
local sphereYCoord = math.random(6, canvasHeight/3)
local sphereDiameter = math.random(10, 40)

-- Shape tool from point to point + diameter
app.useTool {
    tool = "filled_ellipse",
    color = Color{ h=0, s=0, v=1, a=255 },
    brush = brush1,
    points = {
        Point(sphereXCoord, sphereYCoord),
        Point(sphereXCoord + sphereDiameter, sphereYCoord + sphereDiameter)
    },
    cel = cel,
    layer = starLayer
}

------------------------------------------------------------------------------------------------------------------------
-- Create new layer
local buildingsLayer1 = sprite:newLayer()
buildingsLayer1.name = "buildings, 1"
local cel = sprite:newCel(buildingsLayer1, 1)

-- Set building and window parameters
local buildingWidth = canvasWidth/10
local buildingHeight = canvasHeight - (canvasHeight * 0.67)
local buildingStartX = 0
local buildingColour1 = Color{ h=baseHue - math.random(5, 10), s=baseSat + (math.random(5, 10)/100), v=baseVal - (math.random(6, 10)/100), a=255 }

local windowWidth = 2
local windowHeight = 4
local windowColour1a = baseColour
local windowColour1b = baseColour

genBuildings(buildingWidth, buildingHeight, buildingStartX, buildingColour1, windowWidth, windowHeight, windowColour1a, windowColour1b)

------------------------------------------------------------------------------------------------------------------------
-- Create new layer
local roadsBackgroundLayer1 = sprite:newLayer()
roadsBackgroundLayer1.name = "roads, 1"
local cel = sprite:newCel(roadsBackgroundLayer1, 1)

local roadPositionMin = canvasHeight * 0.40
local roadPositionMax = canvasHeight * 0.45
local roadThickness = 2
local roadColour = buildingColour1
local roadPositionY1 = math.random(roadPositionMin, roadPositionMax)

genRoad(roadPositionY1, roadThickness, roadColour)

------------------------------------------------------------------------------------------------------------------------
-- Create new layer
local buildingsLayer2 = sprite:newLayer()
buildingsLayer2.name = "buildings, 2"
local cel = sprite:newCel(buildingsLayer2, 1)
local layer = buildingsLayer2

-- Set building and window parameters
local buildingWidth = canvasWidth/9
local buildingHeight = canvasHeight - (canvasHeight * 0.60)
local buildingStartX = 0
local buildingColour2 = Color{ h=baseHue - math.random(10, 15), s=baseSat + (math.random(5, 10)/100), v=baseVal - (math.random(15, 25)/100), a=255 }

local windowWidth = 3
local windowHeight = 5
local windowColour2a = baseColour
local windowColour2b = buildingColour1

genBuildings(buildingWidth, buildingHeight, buildingStartX, buildingColour2, windowWidth, windowHeight, windowColour2a, windowColour2b)

------------------------------------------------------------------------------------------------------------------------
-- Create new layer
local roadsBackgroundLayer2 = sprite:newLayer()
roadsBackgroundLayer2.name = "roads, 2"
local cel = sprite:newCel(roadsBackgroundLayer2, 1)


local roadPositionMin = canvasHeight * 0.45
local roadPositionMax = canvasHeight * 0.50
local roadThickness = 3
local roadColour = buildingColour2
local roadPositionY2 = math.random(roadPositionMin, roadPositionMax)

genRoad(roadPositionY2, roadThickness, roadColour)

------------------------------------------------------------------------------------------------------------------------
-- Create new layer
local buildingsLayer3 = sprite:newLayer()
buildingsLayer3.name = "buildings, 3"
local cel = sprite:newCel(buildingsLayer3, 1)
local layer = buildingsLayer3

-- Set building and window parameters
local buildingWidth = canvasWidth/8
local buildingHeight = canvasHeight - (canvasHeight * 0.59)
local buildingStartX = 0
local buildingColour3 = Color{ h=baseHue - math.random(15, 20), s=baseSat + (math.random(5, 10)/100), v=baseVal - (math.random(15, 25)/100), a=255 }

local windowWidth = 4
local windowHeight = 6
local windowColour3a = buildingColour1
local windowColour3b = buildingColour2

genBuildings(buildingWidth, buildingHeight, buildingStartX, buildingColour3, windowWidth, windowHeight, windowColour3a, windowColour3b)

------------------------------------------------------------------------------------------------------------------------
-- Create new layer
local roadsBackgroundLayer3 = sprite:newLayer()
roadsBackgroundLayer3.name = "roads, 3"
local cel = sprite:newCel(roadsBackgroundLayer3, 1)

local roadPositionMin = canvasHeight * 0.50
local roadPositionMax = canvasHeight * 0.55
local roadThickness = 3
local roadColour = buildingColour3
local roadPositionY3 = math.random(roadPositionMin, roadPositionMax)

genRoad(roadPositionY3, roadThickness, roadColour)

------------------------------------------------------------------------------------------------------------------------
-- Create new layer
local buildingsLayer4 = sprite:newLayer()
buildingsLayer4.name = "buildings, 4"
local cel = sprite:newCel(buildingsLayer4, 1)
local layer = buildingsLayer4

-- Set building and window parameters
local buildingWidth = canvasWidth/7
local buildingHeight = canvasHeight - (canvasHeight * 0.50)
local buildingStartX = math.random(-20, 0)
local buildingColour4 = Color{ h=baseHue - math.random(20, 25), s=baseSat + (math.random(5, 10)/100), v=baseVal - (math.random(35, 55)/100), a=255 }

local windowWidth = 5
local windowHeight = 7
local windowColour4a = buildingColour2
local windowColour4b = buildingColour3

genBuildings(buildingWidth, buildingHeight, buildingStartX, buildingColour4, windowWidth, windowHeight, windowColour4a, windowColour4b)

------------------------------------------------------------------------------------------------------------------------
-- Create new layer
local roadsBackgroundLayer4 = sprite:newLayer()
roadsBackgroundLayer4.name = "roads, 4"
local cel = sprite:newCel(roadsBackgroundLayer4, 1)

local roadPositionMin = canvasHeight * 0.55
local roadPositionMax = canvasHeight * 0.60
local roadThickness = 4
local roadColour = buildingColour4
local roadPositionY4 = math.random(roadPositionMin, roadPositionMax)

genRoad(roadPositionY4, roadThickness, roadColour)

------------------------------------------------------------------------------------------------------------------------
-- Create new layer
local buildingsLayer5 = sprite:newLayer()
buildingsLayer5.name = "buildings, 5"
local cel = sprite:newCel(buildingsLayer5, 1)
local layer = buildingsLayer5

-- Set building and window parameters
local buildingWidth = canvasWidth/6
local buildingHeight = canvasHeight - (canvasHeight * 0.48)
local buildingStartX = math.random(-40, 0)
local buildingColour5 = Color{ h=baseHue - math.random(30, 45), s=baseSat + (math.random(5, 10)/100), v=baseVal - (math.random(55, 70)/100), a=255 }

local windowWidth = 6
local windowHeight = 8
local windowColour5a = buildingColour3
local windowColour5b = buildingColour4

genBuildings(buildingWidth, buildingHeight, buildingStartX, buildingColour5, windowWidth, windowHeight, windowColour5a, windowColour5b)

------------------------------------------------------------------------------------------------------------------------
-- Create new layer
local roadsBackgroundLayer5 = sprite:newLayer()
roadsBackgroundLayer5.name = "roads, 5"
local cel = sprite:newCel(roadsBackgroundLayer5, 1)

local roadPositionMin = canvasHeight * 0.60
local roadPositionMax = canvasHeight * 0.65
local roadThickness = 6
local roadColour = buildingColour5
local roadPositionY5 = math.random(roadPositionMin, roadPositionMax)

genRoad(roadPositionY5, roadThickness, roadColour)

------------------------------------------------------------------------------------------------------------------------
-- Create new layer
local buildingsLayer6 = sprite:newLayer()
buildingsLayer6.name = "buildings, 6"
local cel = sprite:newCel(buildingsLayer6, 1)
local layer = buildingsLayer6

-- Set building and window parameters
local buildingWidth = canvasWidth/5
local buildingHeight = canvasHeight - (canvasHeight * 0.42)
local buildingStartX = math.random(-40, 40)
local buildingColour6 = Color{ h=baseHue - math.random(50, 70), s=baseSat + (math.random(5, 10)/100), v=baseVal - (math.random(70, 80)/100), a=255 }

local windowWidth = 7
local windowHeight = 9
local windowColour6a = buildingColour5
local windowColour6b = Color{ h=baseHue - math.random(30, 49), s=baseSat, v=baseVal - (math.random(20, 30)/100), a=255 }

genBuildings(buildingWidth, buildingHeight, buildingStartX, buildingColour6, windowWidth, windowHeight, windowColour6a, windowColour6b)

------------------------------------------------------------------------------------------------------------------------
-- Create new layer
local roadsBackgroundLayer6 = sprite:newLayer()
roadsBackgroundLayer6.name = "roads, 6"
local cel = sprite:newCel(roadsBackgroundLayer6, 1)

local roadPositionMin = canvasHeight * 0.65
local roadPositionMax = canvasHeight * 0.70
local roadThickness = 8
local roadColour = buildingColour6
local roadPositionY6 = math.random(roadPositionMin, roadPositionMax)

genRoad(roadPositionY6, roadThickness, roadColour)

------------------------------------------------------------------------------------------------------------------------
local waterLayer = sprite:newLayer()
waterLayer.name = "water"
local cel = sprite:newCel(waterLayer, 1)

app.useTool {
    tool = "filled_rectangle",
    color = buildingColour6,
    brush = brush1,
    points = {
        Point(0, canvasHeight * 0.75),
        Point(canvasWidth, canvasHeight)
    },
    cel = cel,
    layer = waterLayer
}

app.useTool {
    tool = "line",
    color = baseColour,
    brush = brush1,
    points = {
        Point(0, canvasHeight * 0.75),
        Point(canvasWidth, canvasHeight * 0.75)
    },
    cel = cel,
    layer = waterLayer
}

------------------------------------------------------------------------------------------------------------------------
-- Target length is width of canvas, minus 1 to account for existing frame
local targetLength = canvasWidth - 1

for i = 1, targetLength, 1 do
    app.command.NewFrame {}
end

-- Car positions
local tableRoad1Traffic = genTraffic(12, 1)
local tableRoad2Traffic = genTraffic(12, -1)
local tableRoad3Traffic = genTraffic(12, 1)
local tableRoad4Traffic = genTraffic(12, -2)
local tableRoad5Traffic = genTraffic(6, 2)
local tableRoad6Traffic = genTraffic(6, -2)

-- Loop through all frames
local newLength = #sprite.frames
for i = 1, newLength, 1 do

    local frame = sprite.frames[i]

    drawTraffic(tableRoad1Traffic, brush1,   1, roadPositionY1, roadsBackgroundLayer1, roadsBackgroundLayer1.cels[i], i)
    drawTraffic(tableRoad2Traffic, brush1,  -1, roadPositionY2, roadsBackgroundLayer2, roadsBackgroundLayer2.cels[i], i)
    drawTraffic(tableRoad3Traffic, brush1,   1, roadPositionY3, roadsBackgroundLayer3, roadsBackgroundLayer3.cels[i], i)
    drawTraffic(tableRoad4Traffic, brush1,  -2, roadPositionY4, roadsBackgroundLayer4, roadsBackgroundLayer4.cels[i], i)
    drawTraffic(tableRoad5Traffic, brush2,  2, roadPositionY5, roadsBackgroundLayer5, roadsBackgroundLayer5.cels[i], i)
    drawTraffic(tableRoad6Traffic, brush2, -2, roadPositionY6, roadsBackgroundLayer6, roadsBackgroundLayer6.cels[i], i)

end

------------------------------------------------------------------------------------------------------------------------
app.command.FlattenLayers{}

local flattenedLayer = app.activeLayer
app.range.layers = {flattenedLayer}
app.command.Copy{}
app.command.Paste{}

local reflectionLayer = app.activeLayer
reflectionLayer.name = "reflection"
reflectionLayer.opacity = 155
reflectionLayer.blendMode = BlendMode.SCREEN

local oldFrame = app.activeFrame
app.activeLayer = reflectionLayer

tableDirections = {
    "left",
    "hold",
    "right",
    "hold",
    "right",
    "hold",
    "left",
    "hold"
}

for _,cel in ipairs(reflectionLayer.cels) do
    app.activeFrame = cel.frame
    app.command.Flip{ target="mask", orientation="vertical" }
    cel.position = Point(cel.position.x, cel.position.y + (canvasHeight * 0.50) + 1)

    app.useTool {
        tool = "rectangular_marquee",
        brush = brush1,
        points = {
            Point(0, canvasHeight * 0.75),
            Point(canvasWidth, (0))
        },
        cel = cel,
        layer = reflectionLayer
    }

    app.command.Cut{}

    animateReflection(canvasHeight * 0.75)

    if cel.frame.frameNumber % 2 == 0 then
        local moveDir = table.remove(tableDirections)
        table.insert(tableDirections, 1, moveDir)
    end

end -- Closing above loop

------------------------------------------------------------------------------------------------------------------------
app.refresh()

-- Get formatted date and time
local formattedDateAndTime = os.date("%d%m%y %H%M%S")
