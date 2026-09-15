class lol.server.mess.CSM_QCancelQuest extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_QCancelQuest(q_id)
   {
      super();
      this._name = "q_ca";
      this.addProp("q_id",q_id);
   }
}
