class lol.core.quests.QuestTask
{
   var _complete;
   var _qID;
   var _quest;
   var _typeID;
   function QuestTask(type_id, q_id)
   {
      this._typeID = type_id;
      this._qID = q_id;
   }
   function set quest(q)
   {
      this._quest = q;
      this._typeID = q.typeID;
   }
   function get quest()
   {
      return this._quest;
   }
   function get qID()
   {
      return this._qID;
   }
   function get typeID()
   {
      return this._typeID;
   }
   function set complete(c)
   {
      if(c && lol.core.quests.QuestInspector.getInstance().quester.hasQuest(this.typeID,"take"))
      {
         this.quest.cStatus = 2;
      }
      this._complete = c;
   }
   function get complete()
   {
      return this._complete;
   }
}
