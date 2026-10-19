create_display_sql_command = '''

    IF NOT EXISTS
    (
        SELECT *
        FROM SubObjects
        WHERE name = '{display_name}' and ParentObjectID = {factory_talk_view_se_id}
    )
        BEGIN
            DECLARE @sub_objectId		int
            declare @id table			(ID int)


            INSERT INTO SubObjects ([ParentObjectID]
                ,[ParentObjectImport]
                ,[Name]
                ,[DisplayName]
                ,[Type]
                ,[ChangeDate]
                ,[ChangeUser]
                ,[MajorRev]
                ,[MinorRev]
                ,[Lock]
                ,[MarkForDeletion]
                ,[Description]
                ,[OverrideDesc])
            OUTPUT INSERTED.SubObjectID into @ID
            VALUES ({factory_talk_view_se_id},'','{display_name}','Displays','GraphicDisplays','{date_time}','{user}',0,0,NULL,NULL,'ACM Display',0)



            SET @sub_objectID	=(SELECT TOP 1 ID FROM @ID )


            INSERT INTO SubParameters ([SubObjectID]
                ,[Name]
                ,[DataType]
                ,[Value]
                ,[RefType]
                ,[RefImport]
                ,[ChangeDate]
                ,[ChangeUser]
                ,[MajorRev]
                ,[MinorRev]
                ,[ParameterHelp]
                ,[RefValue])
            VALUES (@sub_objectID ,'DisplayTitle','String','Test',1,'','{date_time}','{user}',0,0,'Title of HMI display page',''),
                    (@sub_objectID ,'DisplayLeft','Int','0',1,'','{date_time}','{user}',0,0,'Display X position in pixels',''),
                    (@sub_objectID ,'DisplayTop','Int','0',1,'','{date_time}','{user}',0,0,'Display Y position in pixels',''),
                    (@sub_objectID ,'DisplayWidth','Int','{width}',1,'','{date_time}','{user}',0,0,'Display width in pixels',''),
                    (@sub_objectID ,'DisplayHeight','Int','{height}',1,'','{date_time}','{user}',0,0,'Display height in pixels',''),
                    (@sub_objectID ,'DisplayBackColor','String','silver',1,'','{date_time}','{user}',0,0,'Display background color',''),
                    (@sub_objectID ,'DisplaySecurity','String','*',1,'','{date_time}','{user}',0,0,'Display security',''),
                    (@sub_objectID ,'UpdateRate','Real','1.0',1,'','{date_time}','{user}',0,0,'Display update rate',''),
                    (@sub_objectID ,'LeftIndexMax','Int','7',1,'','{date_time}','{user}',0,0,'Index number of icons per row',''),
                    (@sub_objectID ,'VBAProjectObject','String','',1,'','{date_time}','{user}',0,0,'',''),
                    (@sub_objectID ,'SubObject Description','String','',1,'','{date_time}','{user}',0,0,'','');
        
    END;    
        '''





create_line_sql_command = '''

    IF NOT EXISTS
    (
        SELECT *
        FROM Objects
        WHERE name = '{line_name}' and ParentObjectID = {factory_talk_view_se_id}
    )
        BEGIN
            DECLARE @objectId		int
            declare @id table			(ID int)
            DECLARE @screenObjectId		int

            SET @screenObjectId = (SELECT TOP 1 SubObjectID FROM SubObjects where name = '{display_name}' and ParentObjectID = {factory_talk_view_se_id})


            INSERT INTO Objects ([ProjectID]
                ,[ControllerID]
                ,[ParentObjectID]
                ,[ParentObjectImport]
                ,[Name]
                ,[CatalogNumber]
                ,[Description]
                ,[LibraryID]
                ,[LibraryType]
                ,[ChangeDate]
                ,[ChangeUser])
            OUTPUT INSERTED.ObjectID into @ID
            VALUES ({project_id},{controller_id},'{parent_object_id}','','{line_name}','ProcessLine','Process Line','1E5825D5-62B1-4DF7-BA33-5BA0DDC2DCF3','DesignPattern','{date_time}','{user}')



            SET @objectId	=(SELECT TOP 1 ID FROM @ID )


            INSERT INTO Parameters ([ObjectID]
                ,[Name]
                ,[DataType]
                ,[Value]
                ,[RefType]
                ,[RefImport]
                ,[ChangeDate]
                ,[ChangeUser]
                ,[MajorRev]
                ,[MinorRev]
                ,[ParameterHelp]
                ,[RefValue])
            VALUES (@objectId ,'X1','Int','{X1}',1,'','{date_time}','{user}',0,0,'',''),
                    (@objectId ,'X2','Int','{X2}',1,'','{date_time}','{user}',0,0,'',''),
                    (@objectId ,'Y1','Int','{Y1}',1,'','{date_time}','{user}',0,0,'',''),
                    (@objectId ,'Y2','Int','{Y2}',1,'','{date_time}','{user}',0,0,'',''),
                    (@objectId ,'Color','String','{color}',1,'','{date_time}','{user}',0,0,'',''),
                    (@objectId ,'Width','Int','{width}',1,'','{date_time}','{user}',0,0,'',''),
                    (@objectId ,'SEAssocDisplay','String','',1,'','{date_time}','{user}',0,0,'Associated HMI SE Display',''),
                    (@objectId ,'MEAssocDisplay','String','',1,'','{date_time}','{user}',0,0,'Associated HMI ME Display','');
        

            UPDATE Parameters SET Value = @screenObjectId, RefType = 3 where ObjectID = @objectId and Name = 'SEAssocDisplay'
        
    END;
        '''


create_image_sql_command = '''

    IF NOT EXISTS
    (
        SELECT *
        FROM Objects
        WHERE name = '{image_name}' and ParentObjectID = {parent_object_id}
    )
        BEGIN
            DECLARE @objectId		int
            declare @id table			(ID int)
            DECLARE @screenObjectId		int

            SET @screenObjectId = (SELECT TOP 1 [SubObjectID] FROM SubObjects where name = '{display_name}' and ParentObjectID = {factory_talk_view_se_id})


            INSERT INTO Objects ([ProjectID]
                ,[ControllerID]
                ,[ParentObjectID]
                ,[ParentObjectImport]
                ,[Name]
                ,[CatalogNumber]
                ,[Description]
                ,[LibraryID]
                ,[LibraryType]
                ,[ChangeDate]
                ,[ChangeUser])
            OUTPUT INSERTED.ObjectID into @ID
            VALUES ({project_id},{controller_id},'{parent_object_id}','','{image_name}','Image','HMI Image','F9366DE1-305F-4DCC-BB9E-58C28C019F23','DesignPattern','{date_time}','{user}')



            SET @objectId	=(SELECT TOP 1 ID FROM @ID )


            INSERT INTO Parameters ([ObjectID]
                ,[Name]
                ,[DataType]
                ,[Value]
                ,[RefType]
                ,[RefImport]
                ,[ChangeDate]
                ,[ChangeUser]
                ,[MajorRev]
                ,[MinorRev]
                ,[ParameterHelp]
                ,[RefValue])
            VALUES (@objectId ,'X1','Int','{X1}',1,'','{date_time}','{user}',0,0,'',''),
                    (@objectId ,'X2','Int','{X2}',1,'','{date_time}','{user}',0,0,'',''),
                    (@objectId ,'Y1','Int','{Y1}',1,'','{date_time}','{user}',0,0,'',''),
                    (@objectId ,'Y2','Int','{Y2}',1,'','{date_time}','{user}',0,0,'',''),
                    (@objectId ,'ImageName','String','{filename}',1,'','{date_time}','{user}',0,0,'',''),
                    (@objectId ,'SolutionsProjectAcceleratorID','String','{image_id}',1,'','{date_time}','{user}',0,0,'',''),
                    (@objectId ,'SEAssocDisplay','String','',1,'','{date_time}','{user}',0,0,'Associated HMI SE Display',''),
                    (@objectId ,'MEAssocDisplay','String','',1,'','{date_time}','{user}',0,0,'Associated HMI ME Display','');


            UPDATE Parameters SET Value = @screenObjectId, RefType = 3 where ObjectID = @objectId and Name = 'SEAssocDisplay'

    END;    
        
        '''

create_page_link_sql_command = '''
    IF NOT EXISTS
    (
        SELECT *
        FROM Objects
        WHERE name = '{page_link_name}' and ParentObjectID = {parent_object_id}
    )
        BEGIN
            DECLARE @objectId		int
            declare @id table			(ID int)
            DECLARE @screenObjectId		int

            SET @screenObjectId = (SELECT TOP 1 [SubObjectID] FROM SubObjects where name = '{display_name}' and ParentObjectID = {factory_talk_view_se_id})


            INSERT INTO Objects ([ProjectID]
                ,[ControllerID]
                ,[ParentObjectID]
                ,[ParentObjectImport]
                ,[Name]
                ,[CatalogNumber]
                ,[Description]
                ,[LibraryID]
                ,[LibraryType]
                ,[ChangeDate]
                ,[ChangeUser])
            OUTPUT INSERTED.ObjectID into @ID
            VALUES ({project_id},{controller_id},{parent_object_id},'','{page_link_name}','PageLink','HMI page link','C1A52D94-07A2-4309-80DC-ADB8BB971573','DesignPattern','{date_time}','{user}')



            SET @objectId	=(SELECT TOP 1 ID FROM @ID )


            INSERT INTO Parameters ([ObjectID]
                ,[Name]
                ,[DataType]
                ,[Value]
                ,[RefType]
                ,[RefImport]
                ,[ChangeDate]
                ,[ChangeUser]
                ,[MajorRev]
                ,[MinorRev]
                ,[ParameterHelp]
                ,[RefValue])
            VALUES (@objectId ,'CenterX','Int','{center_x}',1,'','{date_time}','{user}',0,0,'',''),
                    (@objectId ,'CenterY','Int','{center_y}',1,'','{date_time}','{user}',0,0,'',''),
                    (@objectId ,'NavToDisplayName','String','{navigate_to_display_name}',1,'','{date_time}','{user}',0,0,'',''),
                    (@objectId ,'Label','String','{label}',1,'','{date_time}','{user}',0,0,'',''),
                    (@objectId ,'SymbolOrientation','Int','{orientation}',1,'','{date_time}','{user}',0,0,'Process Flow Direction. 0 = left to right (right), 1 = top to bottom (down), 2 = right to left (left), 3 = bottom to top (up)',''),
                    (@objectId ,'SymbolStyle','Int','0',1,'','{date_time}','{user}',0,0,'',''),
                    (@objectId ,'FriendlyName','String','',1,'','{date_time}','{user}',0,0,'',''),
                    (@objectId ,'SolutionsProjectAcceleratorID','String','{page_link_id}',1,'','{date_time}','{user}',0,0,'',''),
                    (@objectId ,'SEAssocDisplay','String','',1,'','{date_time}','{user}',0,0,'Associated HMI SE Display',''),
                    (@objectId ,'MEAssocDisplay','String','',1,'','{date_time}','{user}',0,0,'Associated HMI ME Display','');


            UPDATE Parameters SET Value = @screenObjectId, RefType = 3 where ObjectID = @objectId and Name = 'SEAssocDisplay'
    
    END;     
        
        '''


create_out_page_link_sql_command = '''
    IF NOT EXISTS
    (
        SELECT *
        FROM Objects
        WHERE name = '{page_link_name}'
    )
        BEGIN
            DECLARE @objectId		int
            declare @id table			(ID int)
            DECLARE @screenObjectId		int

            SET @screenObjectId = (SELECT TOP 1 [SubObjectID] FROM SubObjects where name = '{display_name}' and ParentObjectID = {factory_talk_view_se_id})


            INSERT INTO Objects ([ProjectID]
                ,[ControllerID]
                ,[ParentObjectID]
                ,[ParentObjectImport]
                ,[Name]
                ,[CatalogNumber]
                ,[Description]
                ,[LibraryID]
                ,[LibraryType]
                ,[ChangeDate]
                ,[ChangeUser])
            OUTPUT INSERTED.ObjectID into @ID
            VALUES ({project_id},{controller_id},'{parent_object_id}','','{page_link_name}','OutPageLink','HMI page link','BD742C50-7D83-4F28-B77F-4EC4BE912312','DesignPattern','{date_time}','{user}')



            SET @objectId	=(SELECT TOP 1 ID FROM @ID )


            INSERT INTO Parameters ([ObjectID]
                ,[Name]
                ,[DataType]
                ,[Value]
                ,[RefType]
                ,[RefImport]
                ,[ChangeDate]
                ,[ChangeUser]
                ,[MajorRev]
                ,[MinorRev]
                ,[ParameterHelp]
                ,[RefValue])
            VALUES (@objectId ,'CenterX','Int','{center_x}',1,'','{date_time}','{user}',0,0,'',''),
                    (@objectId ,'CenterY','Int','{center_y}',1,'','{date_time}','{user}',0,0,'',''),
                    (@objectId ,'NavToDisplayName','String','{navigate_to_display_name}',1,'','{date_time}','{user}',0,0,'',''),
                    (@objectId ,'Label','String','{label}',1,'','{date_time}','{user}',0,0,'',''),
                    (@objectId ,'SEAssocDisplay','String','',1,'','{date_time}','{user}',0,0,'Associated HMI SE Display',''),
                    (@objectId ,'MEAssocDisplay','String','',1,'','{date_time}','{user}',0,0,'Associated HMI ME Display','');


            UPDATE Parameters SET Value = @screenObjectId, RefType = 3 where ObjectID = @objectId and Name = 'SEAssocDisplay'
    
    END;     
        
        '''


get_display_objects_sql_command = '''
    SELECT 
        Objects.ObjectID,
        Objects.Name,
        Objects.CatalogNumber,
        Objects.Description,
        Objects.LibraryType,
        Objects.LibraryID,
        Objects.ControllerID,
        SubObjects.Name as DisplayName,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'Cfg_PositionX') as Cfg_PositionX,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'Cfg_PositionY') as Cfg_PositionY,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'isPositioned') as isPositioned,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'CenterX') as CenterX,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'CenterY') as CenterY,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'SolutionsProjectAcceleratorID') as SolutionsProjectAcceleratorID,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'X1') as X1,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'Y1') as Y1,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'X2') as X2,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'Y2') as Y2
    FROM 
        Objects
    INNER JOIN 
        Parameters ON Objects.ObjectID = Parameters.ObjectID
    INNER JOIN 
        SubObjects ON Parameters.Value = CAST(SubObjects.SubObjectID AS VARCHAR)
    WHERE 
        Parameters.RefType = 3
        AND SubObjects.ParentObjectID = {factory_talk_view_se_id}
        AND SubObjects.Name = '{display_name}'
    ORDER BY 
        Objects.Name
'''


get_display_object_sql_command = '''
    SELECT 
        Objects.ObjectID,
        Objects.Name,
        Objects.CatalogNumber,
        Objects.Description,
        Objects.LibraryType,
        Objects.LibraryID,
        Objects.ControllerID,
        SubObjects.Name as DisplayName,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'Cfg_PositionX') as Cfg_PositionX,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'Cfg_PositionY') as Cfg_PositionY,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'isPositioned') as isPositioned,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'CenterX') as CenterX,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'CenterY') as CenterY,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'SolutionsProjectAcceleratorID') as SolutionsProjectAcceleratorID,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'X1') as X1,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'Y1') as Y1,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'X2') as X2,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'Y2') as Y2
    FROM 
        Objects
    INNER JOIN 
        Parameters ON Objects.ObjectID = Parameters.ObjectID
    INNER JOIN 
        SubObjects ON Parameters.Value = CAST(SubObjects.SubObjectID AS VARCHAR)
    WHERE 
        Parameters.RefType = 3
        AND Objects.ObjectID = '{object_id}'
    ORDER BY 
        Objects.Name
'''


get_displays_sql_command = '''
    SELECT 
        SubObjects.SubObjectID,
        SubObjects.Name as DisplayName,
        SubObjects.DisplayName as DisplayType,
        SubObjects.Type,
        SubObjects.Description,
        SubObjects.ChangeDate,
        SubObjects.ChangeUser,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplayWidth') as DisplayWidth,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplayHeight') as DisplayHeight,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplayTitle') as DisplayTitle,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplayLeft') as DisplayLeft,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplayTop') as DisplayTop,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplaySecurity') as DisplaySecurity,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplayBackColor') as DisplayBackColor
    FROM 
        SubObjects
    WHERE 
        SubObjects.ParentObjectID = {factory_talk_view_se_id}
    ORDER BY 
        SubObjects.Name
'''


get_display_sql_command = '''
    SELECT 
        SubObjects.SubObjectID,
        SubObjects.Name as DisplayName,
        SubObjects.DisplayName as DisplayType,
        SubObjects.Type,
        SubObjects.Description,
        SubObjects.ChangeDate,
        SubObjects.ChangeUser,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplayWidth') as DisplayWidth,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplayHeight') as DisplayHeight,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplayTitle') as DisplayTitle,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplayLeft') as DisplayLeft,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplayTop') as DisplayTop,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplaySecurity') as DisplaySecurity,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplayBackColor') as DisplayBackColor
    FROM 
        SubObjects
    WHERE 
        SubObjects.ParentObjectID = {factory_talk_view_se_id} and SubObjects.Name = '{display_name}'
    ORDER BY 
        SubObjects.Name
'''


position_control_module_sql_command = '''
            DECLARE @screenObjectId		int

            SET @screenObjectId = (SELECT TOP 1 [SubObjectID] FROM SubObjects where name = '{display_name}' and ParentObjectID = {factory_talk_view_se_id})

            UPDATE Parameters SET Value = @screenObjectId, RefType = 3, ChangeDate = '{date_time}', ChangeUser = '{user}'  where ObjectID = {control_module_id} and Name = 'AssocDisplay'
            UPDATE Parameters SET Value = '{position_x}', ChangeDate = '{date_time}', ChangeUser = '{user}' where ObjectID = {control_module_id} and Name = 'Cfg_PositionX'
            UPDATE Parameters SET Value = '{position_y}', ChangeDate = '{date_time}', ChangeUser = '{user}' where ObjectID = {control_module_id} and Name = 'Cfg_PositionY'
            UPDATE Parameters SET Value = '{orientation}', ChangeDate = '{date_time}', ChangeUser = '{user}' where ObjectID = {control_module_id} and Name = 'SymbolOrientation'
            UPDATE Parameters SET Value = 1, ChangeDate = '{date_time}', ChangeUser = '{user}' where ObjectID = {control_module_id} and Name = 'isPositioned'  
        '''      


write_parameter_value_sql_command = '''
    UPDATE Parameters
    SET Value = '{value}'

    WHERE ObjectID = {object_id} and Name = '{parameter}'
'''


write_parameter_value_and_reftype_sql_command = '''
    UPDATE Parameters
    SET Value = '{value}', RefType = {ref_type}, RefValue = '{ref_value}'
    
    WHERE ObjectID = {object_id} and Name = '{parameter}'
'''


get_all_parameters_of_object = '''
            SELECT * FROM Parameters where ObjectID = (select ObjectID from Objects where Name ='{object_name}') ORDER BY ObjectID ASC
            '''

get_all_subobjects_of_object = '''
            SELECT * FROM SubObjects where ParentObjectID = (select ObjectID from Objects where Name ='{object_name}') ORDER BY SubObjectID
            '''

get_all_subobjects_of_object = '''SELECT * FROM SubParameters where SubObjectID IN
            (SELECT SubObjectID FROM SubObjects where ParentObjectID = (select ObjectID from Objects where Name ='{object_name}'))
            and SubObjectID = (SELECT SubObjectID FROM SubObjects where Name ='{subobject_name_with_index}' AND ParentObjectID =(select ObjectID from Objects where Name ='{object_name}') )
            '''

get_object = '''
            SELECT * FROM Objects where Name ='{object_name}'
            '''

get_all_objects = '''
            SELECT Objects.ObjectID, Objects.Name FROM Objects
            inner join RegisteredLibraries on Objects.LibraryID = RegisteredLibraries.LibraryID 
            where Objects.ProjectID = '{project_id}'
            '''

get_all_objects_with_acm_filter = '''
            SELECT Objects.ObjectID, Objects.Name FROM Objects
            inner join RegisteredLibraries on Objects.LibraryID = RegisteredLibraries.LibraryID 
            where Objects.ProjectID = '{project_id}'
            {filter}
            '''

get_all_subobjects_with_acm_filter = '''
            SELECT SubObjects.SubObjectID
                , SubObjects.ParentObjectID
                , SubObjects.Name
                , SubObjects.DisplayName
                , Objects.ObjectID
                , Objects.Name as ObjectName  FROM SubObjects
            inner join Objects on SubObjects.ParentObjectID = Objects.ObjectID 
            inner join RegisteredLibraries on Objects.LibraryID = RegisteredLibraries.LibraryID 
            where Objects.ProjectID = '{project_id}'
            {filter}
            '''

create_subobject = '''

            IF NOT EXISTS
                (
                    SELECT *
                    FROM SubObjects
                    WHERE name = '{subobject_name}' and ParentObjectID = {parent_object_id}
                )

                BEGIN
                        DECLARE @sub_objectId		int
                        declare @id table			(ID int)


                        INSERT INTO SubObjects ([ParentObjectID]
                            ,[ParentObjectImport]
                            ,[Name]
                            ,[DisplayName]
                            ,[Type]
                            ,[ChangeDate]
                            ,[ChangeUser]
                            ,[MajorRev]
                            ,[MinorRev]
                            ,[Lock]
                            ,[MarkForDeletion]
                            ,[Description]
                            ,[OverrideDesc])
                        OUTPUT INSERTED.SubObjectID into @ID
                        VALUES ({parent_object_id},'','{subobject_name}','{subobject_display_name}','{subobject_type}','{date_time}','{user}',NULL,NULL,NULL,NULL,'{subobject_description}',{description_override})


                        SET @sub_objectID	=(SELECT TOP 1 ID FROM @ID )

                        INSERT INTO SubParameters ([SubObjectID]
                            ,[Name]
                            ,[DataType]
                            ,[Value]
                            ,[RefType]
                            ,[RefImport]
                            ,[ChangeDate]
                            ,[ChangeUser]
                            ,[MajorRev]
                            ,[MinorRev]
                            ,[ParameterHelp]
                            ,[RefValue])

                        VALUES {subparameter_values};

                END;
            '''

delete_subobject_sql_command = '''
    IF EXISTS
    (
        SELECT *
        FROM SubObjects
        WHERE SubObjectID = {subobject_id}
    )
    BEGIN
        DELETE FROM SubParameters WHERE SubObjectID = {subobject_id}
        DELETE FROM SubObjects WHERE SubObjectID = {subobject_id}
    END;
'''


subobject_subparameter_value_template =''' (@sub_objectID , '{name}', '{data_type}', '{value}', {ref_type}, '', '{change_date}', '{user}', NULL, NULL, '{parameter_help}', '{ref_value}')
                '''

write_subparameter_value_sql_command = '''
    UPDATE SubParameters
    SET Value = '{value}' 

    WHERE SubObjectID = {subobject_id} and Name = '{subparameter}'
'''

write_subparameter_value_and_reftype_sql_command = '''
    UPDATE SubParameters
    SET Value = '{value}', RefType = {ref_type}, RefValue = '{ref_value}'

    WHERE SubObjectID = {subobject_id} and Name = '{subparameter}'
'''
