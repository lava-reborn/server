class lol.server.mess.CSM_QGetQuest extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_QGetQuest(q_idx, npcID)
   {
      super();
      this._name = "q_st";
      this.addProp("mob",npcID);
      this.addProp("q_idx",q_idx);
   }
}
