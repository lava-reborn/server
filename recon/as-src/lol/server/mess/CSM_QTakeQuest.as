class lol.server.mess.CSM_QTakeQuest extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_QTakeQuest(q_id, npcID, obj_idx)
   {
      super();
      this._name = "q_co";
      this.addProp("obj_idx",obj_idx);
      this.addProp("mob",npcID);
      this.addProp("q_id",q_id);
   }
}
